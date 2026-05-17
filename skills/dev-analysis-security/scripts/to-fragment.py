#!/usr/bin/env python3
"""Normalize the security tools into one dev-report-fragment/v1 fragment.

Usage:
  to-fragment.py <id> <out_path> [--network FILE] [--gitleaks FILE]
                                 [--trufflehog FILE] [--semgrep FILE]

Folds the static network egress/ingress inventory, gitleaks and trufflehog
secret findings, and the shared run-semgrep.sh taint/network raw into a single
`category: security` attack-surface fragment. Data-flow is part of this Skill,
not a separate one — taint paths, network surface, and secrets land in one
fragment. Writes factual metrics{} and factual body[]; threat-synthesis.md
enriches `summary` and adds the narrative body[] afterward.

Any verified secret (gitleaks finding or trufflehog verified result) makes the
fragment status:error and exits 4.

Exit codes:
  0  fragment written; status ok/warn
  1  bad arguments
  2  a provided raw file was unparseable; nothing written
  4  verified secret(s) present; fragment written with status error
"""
import datetime
import json
import pathlib
import sys

SEMGREP_SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "ERROR": 2}
KNOWN_FLAGS = ("--network", "--gitleaks", "--trufflehog", "--semgrep")


def _load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _load_json_lines(path):
    records = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _parse_network(path):
    data = _load_json(path)
    egress = [
        {
            "signature": hit.get("signature", ""),
            "path": hit.get("path", ""),
            "line": hit.get("line", 0),
            "code": hit.get("code", ""),
        }
        for hit in data.get("egress", [])
    ]
    ingress = [
        {
            "signature": hit.get("signature", ""),
            "path": hit.get("path", ""),
            "line": hit.get("line", 0),
            "code": hit.get("code", ""),
        }
        for hit in data.get("ingress", [])
    ]
    return egress, ingress


def _parse_gitleaks(path):
    data = _load_json(path)
    records = data if isinstance(data, list) else data.get("findings", []) or []
    findings = []
    for record in records:
        findings.append(
            {
                "rule": record.get("RuleID", record.get("Description", "")),
                "path": record.get("File", ""),
                "line": record.get("StartLine", 0),
                "secret": "redacted",
                "source": "gitleaks",
            }
        )
    return findings


def _parse_trufflehog(path):
    records = _load_json_lines(path)
    findings = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if not record.get("Verified", False):
            continue
        source_metadata = record.get("SourceMetadata", {}) or {}
        data = source_metadata.get("Data", {}) or {}
        filesystem = data.get("Filesystem", {}) or {}
        findings.append(
            {
                "rule": record.get("DetectorName", ""),
                "path": filesystem.get("file", ""),
                "line": filesystem.get("line", 0),
                "secret": "verified",
                "source": "trufflehog",
            }
        )
    return findings


def _parse_semgrep(path):
    data = _load_json(path)
    findings = []
    counts = {"error": 0, "warning": 0, "info": 0}
    for result in data.get("results", []):
        extra = result.get("extra", {}) or {}
        severity = str(extra.get("severity", "INFO")).upper()
        bucket = {"ERROR": "error", "WARNING": "warning"}.get(severity, "info")
        counts[bucket] += 1
        findings.append(
            {
                "check": result.get("check_id", ""),
                "path": result.get("path", ""),
                "line": (result.get("start", {}) or {}).get("line", 0),
                "severity": severity,
                "message": str(extra.get("message", "")).strip().replace("\n", " "),
            }
        )
    findings.sort(
        key=lambda f: (-SEMGREP_SEVERITY_RANK.get(f["severity"], 0), f["path"], f["line"])
    )
    return findings, counts


def _parse_args(argv):
    if len(argv) < 2:
        return None
    parsed = {"id": argv[0], "out_path": argv[1], "raw": {}}
    rest = argv[2:]
    index = 0
    while index < len(rest):
        flag = rest[index]
        if flag in KNOWN_FLAGS:
            if index + 1 >= len(rest):
                sys.stderr.write(f"missing value for {flag}\n")
                return None
            parsed["raw"][flag[2:]] = rest[index + 1]
            index += 2
        else:
            sys.stderr.write(f"unknown argument: {flag}\n")
            return None
    return parsed


def main():
    parsed = _parse_args(sys.argv[1:])
    if parsed is None:
        sys.stderr.write(
            "usage: to-fragment.py <id> <out_path> [--network FILE] "
            "[--gitleaks FILE] [--trufflehog FILE] [--semgrep FILE]\n"
        )
        return 1

    fragment_id = parsed["id"]
    out_path = pathlib.Path(parsed["out_path"])
    raw = parsed["raw"]

    metrics = {}
    body = []
    status = "ok"
    secret_findings = []

    try:
        if "network" in raw:
            egress, ingress = _parse_network(raw["network"])
            metrics["network_egress"] = len(egress)
            metrics["network_ingress"] = len(ingress)
            body.append(
                {
                    "type": "metric-cards",
                    "title": "Network surface",
                    "cards": [
                        {"label": "Outbound calls", "value": len(egress), "delta_metric": "network_egress"},
                        {"label": "Inbound listeners", "value": len(ingress), "delta_metric": "network_ingress"},
                    ],
                }
            )
            body.append(
                {
                    "type": "table",
                    "title": "Outbound network calls",
                    "filterable": True,
                    "columns": [
                        {"key": "signature", "label": "Signature", "type": "string", "sortable": True},
                        {"key": "path", "label": "File", "type": "string", "sortable": True},
                        {"key": "line", "label": "Line", "type": "number", "sortable": True},
                        {"key": "code", "label": "Call site", "type": "string", "sortable": False},
                    ],
                    "rows": egress,
                    "defaultSort": {"key": "signature", "dir": "asc"},
                }
            )
            body.append(
                {
                    "type": "table",
                    "title": "Inbound network listeners",
                    "filterable": True,
                    "columns": [
                        {"key": "signature", "label": "Signature", "type": "string", "sortable": True},
                        {"key": "path", "label": "File", "type": "string", "sortable": True},
                        {"key": "line", "label": "Line", "type": "number", "sortable": True},
                        {"key": "code", "label": "Bind site", "type": "string", "sortable": False},
                    ],
                    "rows": ingress,
                    "defaultSort": {"key": "signature", "dir": "asc"},
                }
            )
            if egress or ingress:
                status = "warn"

        if "gitleaks" in raw:
            secret_findings.extend(_parse_gitleaks(raw["gitleaks"]))
        if "trufflehog" in raw:
            secret_findings.extend(_parse_trufflehog(raw["trufflehog"]))

        if "gitleaks" in raw or "trufflehog" in raw:
            metrics["secrets"] = len(secret_findings)
            secret_findings.sort(key=lambda f: (f["source"], f["path"], f["line"]))
            body.append(
                {
                    "type": "metric-cards",
                    "title": "Secrets",
                    "cards": [
                        {"label": "Verified secrets", "value": len(secret_findings), "delta_metric": "secrets"},
                    ],
                }
            )
            body.append(
                {
                    "type": "table",
                    "title": "Secret findings",
                    "filterable": True,
                    "columns": [
                        {"key": "rule", "label": "Rule", "type": "string", "sortable": True},
                        {"key": "path", "label": "File", "type": "string", "sortable": True},
                        {"key": "line", "label": "Line", "type": "number", "sortable": True},
                        {"key": "source", "label": "Scanner", "type": "string", "sortable": True},
                    ],
                    "rows": secret_findings,
                    "defaultSort": {"key": "source", "dir": "asc"},
                }
            )

        if "semgrep" in raw:
            findings, counts = _parse_semgrep(raw["semgrep"])
            metrics["semgrep_error"] = counts["error"]
            metrics["semgrep_warning"] = counts["warning"]
            metrics["semgrep_info"] = counts["info"]
            metrics["semgrep_findings"] = sum(counts.values())
            body.append(
                {
                    "type": "metric-cards",
                    "title": "Semgrep taint/security findings",
                    "cards": [
                        {"label": "Error", "value": counts["error"], "delta_metric": "semgrep_error"},
                        {"label": "Warning", "value": counts["warning"], "delta_metric": "semgrep_warning"},
                        {"label": "Info", "value": counts["info"], "delta_metric": "semgrep_info"},
                    ],
                }
            )
            body.append(
                {
                    "type": "table",
                    "title": "Semgrep findings",
                    "filterable": True,
                    "columns": [
                        {"key": "check", "label": "Check", "type": "string", "sortable": True},
                        {"key": "path", "label": "File", "type": "string", "sortable": True},
                        {"key": "line", "label": "Line", "type": "number", "sortable": True},
                        {"key": "severity", "label": "Severity", "type": "string", "sortable": True},
                        {"key": "message", "label": "Message", "type": "string", "sortable": False},
                    ],
                    "rows": findings,
                    "defaultSort": {"key": "severity", "dir": "desc"},
                }
            )
            if counts["error"] > 0 and status != "error":
                status = "warn"
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as error:
        sys.stderr.write(f"unparseable raw input: {error}\n")
        return 2

    if secret_findings:
        status = "error"

    fragment = {
        "schema": "dev-report-fragment/v1",
        "id": fragment_id,
        "category": "security",
        "title": "Attack surface",
        "summary": "",
        "status": status,
        "severity": None,
        "producer": {
            "skill": "dev-analysis-security",
            "tool": "network-extractor+gitleaks+trufflehog+semgrep",
            "version": "1",
        },
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "metrics": metrics,
        "body": body,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {out_path} status={status}")
    return 4 if status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
