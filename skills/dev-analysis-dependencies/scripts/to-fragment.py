#!/usr/bin/env python3
"""Normalize dependency-scanner raw output into one dev-report-fragment/v1 JSON.

Usage: to-fragment.py <id> <raw...> <out_fragment.json>

Accepts one or more raw files produced by the run-*.sh scanners (Dependency-
Check JSON, Trivy JSON, Grype JSON, cargo-audit JSON, cargo-geiger JSON, Syft
CycloneDX/SPDX JSON). Findings from Dependency-Check / Trivy / Grype are
deduplicated by (package, CVE) so an overlapping CVE is counted once, then
grouped per library: the primary table's level-1 rows are libraries and each
library's children are its individual CVE findings. Emits the factual
`metrics{critical,high,medium,low,packages}` and factual `body[]`; the Skill's
references/supply-chain-synthesis.md role enriches `summary` and adds narrative
`body[]`.

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


def _report_help():
    help_path = (
        pathlib.Path(__file__).resolve().parent
        / ".."
        / "references"
        / "report-help.md"
    )
    try:
        return help_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def make_finding(name, version, ecosystem, cve, severity, cvss, source, fixed):
    return {
        "package": name or "unknown",
        "version": version or "",
        "ecosystem": ecosystem or "unknown",
        "cve": cve or "UNKNOWN",
        "severity": severity,
        "cvss": cvss,
        "source": source,
        "fixed": fixed or "",
    }


def parse_dependency_check(document):
    findings = []
    for dependency in document.get("dependencies", []):
        name = dependency.get("fileName") or dependency.get("filePath") or "unknown"
        version = ""
        ecosystem = "unknown"
        for package_id in dependency.get("packages", []):
            identifier = package_id.get("id")
            if identifier:
                name, version, ecosystem = split_purl(identifier, name)
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
                make_finding(name, version, ecosystem, cve, severity, cvss,
                             "Dependency-Check", "")
            )
    return findings


def split_purl(identifier, fallback_name):
    text = str(identifier)
    ecosystem = "unknown"
    if text.startswith("pkg:"):
        text = text[len("pkg:"):]
        if "/" in text:
            ecosystem, text = text.split("/", 1)
    name = text
    version = ""
    if "@" in name:
        name, version = name.rsplit("@", 1)
        version = version.split("?", 1)[0]
    if not name:
        name = fallback_name
    return name, version, ecosystem


def parse_trivy(document):
    findings = []
    for result in document.get("Results", []):
        ecosystem = (
            result.get("Type") or result.get("Class") or "unknown"
        )
        for vulnerability in result.get("Vulnerabilities", []) or []:
            name = vulnerability.get("PkgName") or "unknown"
            version = vulnerability.get("InstalledVersion") or ""
            cvss_score = None
            for vendor in (vulnerability.get("CVSS") or {}).values():
                cvss_score = vendor.get("V3Score") or vendor.get("V2Score")
                if cvss_score is not None:
                    break
            findings.append(
                make_finding(
                    name,
                    version,
                    ecosystem,
                    vulnerability.get("VulnerabilityID") or "UNKNOWN",
                    normalize_severity(vulnerability.get("Severity")),
                    cvss_score,
                    "Trivy",
                    vulnerability.get("FixedVersion") or "",
                )
            )
    return findings


def parse_grype(document):
    findings = []
    for match in document.get("matches", []):
        artifact = match.get("artifact", {})
        name = artifact.get("name") or "unknown"
        version = artifact.get("version") or ""
        ecosystem = artifact.get("type") or "unknown"
        vulnerability = match.get("vulnerability", {})
        cvss_score = None
        for entry in vulnerability.get("cvss", []) or []:
            cvss_score = entry.get("metrics", {}).get("baseScore")
            if cvss_score is not None:
                break
        fixed = ""
        fix = vulnerability.get("fix") or {}
        versions = fix.get("versions") or []
        if versions:
            fixed = ", ".join(str(item) for item in versions)
        findings.append(
            make_finding(
                name,
                version,
                ecosystem,
                vulnerability.get("id") or "UNKNOWN",
                normalize_severity(vulnerability.get("severity")),
                cvss_score,
                "Grype",
                fixed,
            )
        )
    return findings


def parse_cargo_audit(document):
    findings = []
    vulnerabilities = document.get("vulnerabilities", {})
    for entry in vulnerabilities.get("list", []) or []:
        advisory = entry.get("advisory", {})
        package = entry.get("package", {})
        name = package.get("name") or "unknown"
        version = package.get("version") or ""
        cvss = advisory.get("cvss")
        severity = severity_from_cvss(cvss) or "high"
        patched = entry.get("versions", {}).get("patched") or []
        fixed = ", ".join(str(item) for item in patched)
        findings.append(
            make_finding(
                name,
                version,
                "cargo",
                advisory.get("id") or "RUSTSEC-UNKNOWN",
                severity,
                cvss,
                "cargo-audit",
                fixed,
            )
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
            components.append(name)
    for artifact in document.get("artifacts", []) or []:
        name = artifact.get("name")
        if name:
            components.append(name)
    for package in document.get("packages", []) or []:
        name = package.get("name")
        if name and isinstance(package, dict) and "SPDXID" in package:
            components.append(name)
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
        key = (finding["package"], finding["version"], finding["cve"])
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
            if not existing.get("fixed") and finding.get("fixed"):
                existing["fixed"] = finding["fixed"]
            if existing.get("ecosystem") in ("", "unknown") and finding.get("ecosystem"):
                existing["ecosystem"] = finding["ecosystem"]
    return list(by_key.values())


def group_by_library(deduped):
    libraries = {}
    for finding in deduped:
        key = (finding["package"], finding["ecosystem"])
        library = libraries.get(key)
        if library is None:
            library = {
                "package": finding["package"],
                "ecosystem": finding["ecosystem"],
                "versions": set(),
                "findings": [],
            }
            libraries[key] = library
        if finding["version"]:
            library["versions"].add(finding["version"])
        library["findings"].append(finding)
    ordered_libraries = []
    for library in libraries.values():
        worst = min(
            SEVERITY_ORDER.index(item["severity"]) for item in library["findings"]
        )
        library["worst_index"] = worst
        library["worst_severity"] = SEVERITY_ORDER[worst]
        ordered_libraries.append(library)
    ordered_libraries.sort(
        key=lambda lib: (
            lib["worst_index"],
            -len(lib["findings"]),
            lib["package"],
        )
    )
    return ordered_libraries


def build_fragment(fragment_id, deduped, sbom_components, geiger_rows, geiger_total):
    counts = {level: 0 for level in SEVERITY_ORDER}
    for finding in deduped:
        counts[finding["severity"]] += 1

    libraries = group_by_library(deduped)

    package_set = {library["package"] for library in libraries}
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
        f"across {len(libraries)} vulnerable libraries "
        f"({metrics['packages']} packages scanned)."
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

    if libraries:
        body.append(
            {
                "type": "table",
                "title": "Vulnerable libraries (grouped; expand for CVEs)",
                "status": status,
                "filterable": True,
                "columns": [
                    {"key": "library", "label": "Library", "type": "string", "sortable": True},
                    {"key": "versions", "label": "Installed version(s)", "type": "string", "sortable": True},
                    {"key": "severity", "label": "Highest severity", "type": "string", "sortable": True},
                    {"key": "count", "label": "Vuln count", "type": "number", "sortable": True},
                    {"key": "ecosystem", "label": "Ecosystem", "type": "string", "sortable": True},
                ],
                "rows": [
                    {
                        "library": library["package"],
                        "versions": ", ".join(sorted(library["versions"])) or "—",
                        "severity": library["worst_severity"],
                        "count": len(library["findings"]),
                        "ecosystem": library["ecosystem"],
                        "children": [
                            {
                                "library": finding["cve"],
                                "versions": finding["fixed"] or "—",
                                "severity": finding["severity"],
                                "count": 1,
                                "ecosystem": ", ".join(sorted(finding["sources"]))
                                or finding["ecosystem"],
                            }
                            for finding in sorted(
                                library["findings"],
                                key=lambda item: (
                                    SEVERITY_ORDER.index(item["severity"]),
                                    item["cve"],
                                ),
                            )
                        ],
                    }
                    for library in libraries
                ],
                "defaultSort": {"key": "count", "dir": "desc"},
            }
        )

    if geiger_rows:
        metrics["unsafe_expressions"] = geiger_total
        body.append(
            {
                "type": "table",
                "title": "Rust unsafe surface (cargo-geiger)",
                "status": "warn" if geiger_total > 0 else "ok",
                "filterable": True,
                "columns": [
                    {"key": "package", "label": "Crate", "type": "string", "sortable": True},
                    {"key": "unsafe_used", "label": "Unsafe used", "type": "number", "sortable": True},
                ],
                "rows": geiger_rows,
                "defaultSort": {"key": "unsafe_used", "dir": "desc"},
            }
        )

    fragment = {
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
    }
    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md
    return fragment, status


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
