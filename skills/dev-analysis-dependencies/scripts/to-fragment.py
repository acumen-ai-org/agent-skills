#!/usr/bin/env python3
"""Normalize dependency-scanner raw output into one dev-report-fragment/v1 JSON.

Usage: to-fragment.py <id> <raw...> <out_fragment.json>

Accepts one or more raw files produced by the run-*.sh scanners (Dependency-
Check JSON, Trivy JSON, Grype JSON, cargo-audit JSON, cargo-geiger JSON, Syft
CycloneDX/SPDX JSON). Findings from Dependency-Check / Trivy / Grype are
deduplicated by (package, CVE) so an overlapping CVE is counted once. Emits the
factual `metrics{critical,high,medium,low,packages}` and factual `body[]`; the
Skill's references/supply-chain-synthesis.md role enriches `summary` and adds
narrative `body[]`.

Exit codes:
  0  fragment written; status ok/warn (no critical findings)
  1  bad arguments (missing positional)
  2  every raw input was unparseable; raw kept, no fragment written
  4  fragment written with at least one critical finding; status error
"""
import datetime
import json
import pathlib
import sys

SEVERITY_ORDER = ("critical", "high", "medium", "low")
SEVERITY_ALIASES = {
    "critical": "critical",
    "high": "high",
    "moderate": "medium",
    "medium": "medium",
    "low": "low",
    "negligible": "low",
    "informational": "low",
    "info": "low",
    "unknown": "low",
}
SEVERITY_FROM_CVSS = (
    (9.0, "critical"),
    (7.0, "high"),
    (4.0, "medium"),
    (0.0, "low"),
)


def normalize_severity(value):
    if value is None:
        return "low"
    return SEVERITY_ALIASES.get(str(value).strip().lower(), "low")


def severity_from_cvss(score):
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return None
    for threshold, label in SEVERITY_FROM_CVSS:
        if numeric >= threshold:
            return label
    return "low"


def load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def parse_dependency_check(document):
    findings = []
    for dependency in document.get("dependencies", []):
        package = dependency.get("fileName") or dependency.get("filePath") or "unknown"
        for package_id in dependency.get("packages", []):
            identifier = package_id.get("id")
            if identifier:
                package = identifier
                break
        for vulnerability in dependency.get("vulnerabilities", []):
            cve = vulnerability.get("name") or "UNKNOWN"
            severity = normalize_severity(vulnerability.get("severity"))
            cvss = (
                vulnerability.get("cvssv3", {}).get("baseScore")
                if isinstance(vulnerability.get("cvssv3"), dict)
                else None
            )
            findings.append(
                {
                    "package": package,
                    "cve": cve,
                    "severity": severity,
                    "cvss": cvss,
                    "source": "Dependency-Check",
                }
            )
    return findings


def parse_trivy(document):
    findings = []
    for result in document.get("Results", []):
        for vulnerability in result.get("Vulnerabilities", []) or []:
            package = vulnerability.get("PkgName") or "unknown"
            installed = vulnerability.get("InstalledVersion")
            if installed:
                package = f"{package}@{installed}"
            cvss_score = None
            for vendor in (vulnerability.get("CVSS") or {}).values():
                cvss_score = vendor.get("V3Score") or vendor.get("V2Score")
                if cvss_score is not None:
                    break
            findings.append(
                {
                    "package": package,
                    "cve": vulnerability.get("VulnerabilityID") or "UNKNOWN",
                    "severity": normalize_severity(vulnerability.get("Severity")),
                    "cvss": cvss_score,
                    "source": "Trivy",
                }
            )
    return findings


def parse_grype(document):
    findings = []
    for match in document.get("matches", []):
        artifact = match.get("artifact", {})
        package = artifact.get("name") or "unknown"
        version = artifact.get("version")
        if version:
            package = f"{package}@{version}"
        vulnerability = match.get("vulnerability", {})
        cvss_score = None
        for entry in vulnerability.get("cvss", []) or []:
            cvss_score = entry.get("metrics", {}).get("baseScore")
            if cvss_score is not None:
                break
        findings.append(
            {
                "package": package,
                "cve": vulnerability.get("id") or "UNKNOWN",
                "severity": normalize_severity(vulnerability.get("severity")),
                "cvss": cvss_score,
                "source": "Grype",
            }
        )
    return findings


def parse_cargo_audit(document):
    findings = []
    vulnerabilities = document.get("vulnerabilities", {})
    for entry in vulnerabilities.get("list", []) or []:
        advisory = entry.get("advisory", {})
        package = entry.get("package", {})
        name = package.get("name") or "unknown"
        version = package.get("version")
        if version:
            name = f"{name}@{version}"
        cvss = advisory.get("cvss")
        severity = severity_from_cvss(cvss) or "high"
        findings.append(
            {
                "package": name,
                "cve": advisory.get("id") or "RUSTSEC-UNKNOWN",
                "severity": severity,
                "cvss": cvss,
                "source": "cargo-audit",
            }
        )
    return findings


def parse_cargo_geiger(document):
    rows = []
    total_unsafe = 0
    packages = document.get("packages", [])
    for package in packages:
        package_id = package.get("package", {}).get("id", {})
        name = package_id.get("name") or "unknown"
        version = package_id.get("version")
        unsafety = package.get("unsafety", {}).get("used", {})
        functions = unsafety.get("functions", {}).get("unsafe_", 0)
        expressions = unsafety.get("exprs", {}).get("unsafe_", 0)
        used = int(functions) + int(expressions)
        total_unsafe += used
        if used:
            rows.append(
                {
                    "package": f"{name}@{version}" if version else name,
                    "unsafe_used": used,
                }
            )
    return rows, total_unsafe


def parse_sbom(document):
    components = []
    for component in document.get("components", []) or []:
        name = component.get("name")
        if name:
            version = component.get("version")
            components.append(f"{name}@{version}" if version else name)
    for artifact in document.get("artifacts", []) or []:
        name = artifact.get("name")
        if name:
            version = artifact.get("version")
            components.append(f"{name}@{version}" if version else name)
    for package in document.get("packages", []) or []:
        name = package.get("name")
        if name and isinstance(package, dict) and "SPDXID" in package:
            version = package.get("versionInfo")
            components.append(f"{name}@{version}" if version else name)
    return components


def classify(document):
    if not isinstance(document, dict):
        return None
    if "dependencies" in document and isinstance(document["dependencies"], list):
        if document["dependencies"] and isinstance(document["dependencies"][0], dict) and "vulnerabilities" in document["dependencies"][0] or "scanInfo" in document:
            return "dependency-check"
    if "Results" in document or "SchemaVersion" in document and "ArtifactName" in document:
        return "trivy"
    if "matches" in document and "descriptor" in document:
        return "grype"
    if "vulnerabilities" in document and isinstance(document.get("vulnerabilities"), dict):
        return "cargo-audit"
    if "packages" in document and document.get("packages") and isinstance(document["packages"][0], dict) and "unsafety" in document["packages"][0]:
        return "cargo-geiger"
    if "bomFormat" in document or "spdxVersion" in document or "artifacts" in document:
        return "sbom"
    if "Results" in document:
        return "trivy"
    return None


def dedupe(findings):
    by_key = {}
    for finding in findings:
        key = (finding["package"], finding["cve"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = dict(finding)
            by_key[key]["sources"] = {finding["source"]}
        else:
            existing["sources"].add(finding["source"])
            if SEVERITY_ORDER.index(finding["severity"]) < SEVERITY_ORDER.index(
                existing["severity"]
            ):
                existing["severity"] = finding["severity"]
            if existing.get("cvss") is None and finding.get("cvss") is not None:
                existing["cvss"] = finding["cvss"]
    return list(by_key.values())


def build_fragment(fragment_id, deduped, sbom_components, geiger_rows, geiger_total):
    counts = {level: 0 for level in SEVERITY_ORDER}
    for finding in deduped:
        counts[finding["severity"]] += 1

    package_set = {finding["package"] for finding in deduped}
    package_set.update(sbom_components)
    package_set.update(row["package"] for row in geiger_rows)

    metrics = {
        "critical": counts["critical"],
        "high": counts["high"],
        "medium": counts["medium"],
        "low": counts["low"],
        "packages": len(package_set),
    }

    if counts["critical"] > 0:
        status = "error"
        severity = 90
    elif counts["high"] > 0:
        status = "warn"
        severity = 60
    elif counts["medium"] > 0 or counts["low"] > 0:
        status = "warn"
        severity = 30
    else:
        status = "ok"
        severity = 0

    total = sum(counts.values())
    summary = (
        f"{total} unique vulnerable dependency findings "
        f"({counts['critical']} critical, {counts['high']} high, "
        f"{counts['medium']} medium, {counts['low']} low) "
        f"across {metrics['packages']} packages."
    )

    body = [
        {
            "type": "metric-cards",
            "title": "Vulnerability severity",
            "cards": [
                {"label": "Critical", "value": counts["critical"], "delta_metric": "critical"},
                {"label": "High", "value": counts["high"], "delta_metric": "high"},
                {"label": "Medium", "value": counts["medium"], "delta_metric": "medium"},
                {"label": "Low", "value": counts["low"], "delta_metric": "low"},
                {"label": "Packages", "value": metrics["packages"], "delta_metric": "packages"},
            ],
        }
    ]

    if deduped:
        ordered = sorted(
            deduped,
            key=lambda finding: (
                SEVERITY_ORDER.index(finding["severity"]),
                finding["package"],
            ),
        )
        body.append(
            {
                "type": "table",
                "title": "Vulnerable dependencies (deduplicated by package + CVE)",
                "filterable": True,
                "columns": [
                    {"key": "package", "label": "Package", "type": "string", "sortable": True},
                    {"key": "cve", "label": "CVE / advisory", "type": "string", "sortable": True},
                    {"key": "severity", "label": "Severity", "type": "string", "sortable": True},
                    {"key": "cvss", "label": "CVSS", "type": "number", "sortable": True},
                    {"key": "sources", "label": "Reported by", "type": "string", "sortable": True},
                ],
                "rows": [
                    {
                        "package": finding["package"],
                        "cve": finding["cve"],
                        "severity": finding["severity"],
                        "cvss": finding.get("cvss") if isinstance(finding.get("cvss"), (int, float)) else 0,
                        "sources": ", ".join(sorted(finding["sources"])),
                    }
                    for finding in ordered
                ],
                "defaultSort": {"key": "severity", "dir": "asc"},
            }
        )

    if geiger_rows:
        metrics["unsafe_expressions"] = geiger_total
        body.append(
            {
                "type": "table",
                "title": "Rust unsafe surface (cargo-geiger)",
                "filterable": True,
                "columns": [
                    {"key": "package", "label": "Crate", "type": "string", "sortable": True},
                    {"key": "unsafe_used", "label": "Unsafe used", "type": "number", "sortable": True},
                ],
                "rows": geiger_rows,
                "defaultSort": {"key": "unsafe_used", "dir": "desc"},
            }
        )

    return {
        "schema": "dev-report-fragment/v1",
        "id": fragment_id,
        "category": "dependencies",
        "title": "Dependency supply-chain scan",
        "summary": summary,
        "status": status,
        "severity": severity,
        "producer": {
            "skill": "dev-analysis-dependencies",
            "tool": "depcheck+trivy+grype+cargo",
            "version": "v1",
        },
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": metrics,
        "body": body,
    }, status


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: to-fragment.py <id> <raw...> <out_fragment.json>\n")
        return 1

    fragment_id = sys.argv[1]
    raw_paths = sys.argv[2:-1]
    out_path = pathlib.Path(sys.argv[-1])

    if not raw_paths:
        sys.stderr.write("usage: to-fragment.py <id> <raw...> <out_fragment.json>\n")
        return 1

    all_findings = []
    sbom_components = []
    geiger_rows = []
    geiger_total = 0
    parsed_any = False

    for raw_path in raw_paths:
        document = load_json(raw_path)
        kind = classify(document)
        if kind is None:
            sys.stderr.write(f"skipped unparseable raw input: {raw_path}\n")
            continue
        parsed_any = True
        if kind == "dependency-check":
            all_findings.extend(parse_dependency_check(document))
        elif kind == "trivy":
            all_findings.extend(parse_trivy(document))
        elif kind == "grype":
            all_findings.extend(parse_grype(document))
        elif kind == "cargo-audit":
            all_findings.extend(parse_cargo_audit(document))
        elif kind == "cargo-geiger":
            rows, total = parse_cargo_geiger(document)
            geiger_rows.extend(rows)
            geiger_total += total
        elif kind == "sbom":
            sbom_components.extend(parse_sbom(document))

    if not parsed_any:
        sys.stderr.write("no parseable raw input; fragment not written\n")
        return 2

    deduped = dedupe(all_findings)
    fragment, status = build_fragment(
        fragment_id, deduped, sbom_components, geiger_rows, geiger_total
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} status={status}")
    return 4 if status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
