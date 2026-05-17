#!/usr/bin/env python3
"""Normalize quality tool output into one dev-report-fragment/v1 fragment.

Usage:
  to-fragment.py <id> <out_path> [--semgrep FILE] [--scc FILE]
                                  [--opa FILE] [--conftest FILE]

Rolls Semgrep findings, scc size/complexity, and OPA/Conftest policy
results into a single `category: quality` fragment. Writes the factual
metrics{} and factual body[]; the quality-synthesis.md role enriches
`summary` and adds narrative body[] afterward.

Exit codes:
  0  fragment written; status ok/warn
  1  bad arguments
  2  a provided raw file was unparseable; nothing written
  4  blocking findings present; fragment written with status error
"""
import datetime
import json
import pathlib
import sys

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "ERROR": 2}


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _parse_semgrep(path):
    data = _load(path)
    findings = []
    counts = {"error": 0, "warning": 0, "info": 0}
    for result in data.get("results", []):
        extra = result.get("extra", {})
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
        key=lambda f: (-SEVERITY_RANK.get(f["severity"], 0), f["path"], f["line"])
    )
    return findings, counts


def _parse_scc(path):
    data = _load(path)
    languages = data if isinstance(data, list) else data.get("languages", [])
    total_code = 0
    total_complexity = 0
    total_files = 0
    per_language = []
    for entry in languages:
        code = int(entry.get("Code", 0))
        complexity = int(entry.get("Complexity", 0))
        files = entry.get("Count")
        if files is None:
            files = len(entry.get("Files", []) or [])
        total_code += code
        total_complexity += complexity
        total_files += int(files)
        per_language.append(
            {
                "language": entry.get("Name", ""),
                "files": int(files),
                "code": code,
                "complexity": complexity,
            }
        )
    per_language.sort(key=lambda r: (-r["code"], r["language"]))
    return {
        "loc_code": total_code,
        "complexity": total_complexity,
        "files": total_files,
        "per_language": per_language,
    }


def _parse_policy(path, tool):
    data = _load(path)
    failures = 0
    rows = []
    if tool == "conftest":
        records = data if isinstance(data, list) else [data]
        for record in records:
            filename = record.get("filename", "")
            for failure in record.get("failures", []) or []:
                failures += 1
                rows.append({"file": filename, "rule": failure.get("msg", "")})
            for warning in record.get("warnings", []) or []:
                rows.append({"file": filename, "rule": warning.get("msg", "")})
    else:
        result = data.get("result", [])
        for expression in result:
            value = expression.get("expressions", [{}])
            for item in value:
                payload = item.get("value", {})
                deny = []
                if isinstance(payload, dict):
                    for key in ("deny", "violation"):
                        deny.extend(payload.get(key, []) or [])
                for entry in deny:
                    failures += 1
                    rows.append({"file": "", "rule": str(entry)})
    return failures, rows


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.stderr.write(
            "usage: to-fragment.py <id> <out_path> "
            "[--semgrep FILE] [--scc FILE] [--opa FILE] [--conftest FILE]\n"
        )
        return 1

    fragment_id = args[0]
    out_path = pathlib.Path(args[1])
    raw = {}
    rest = args[2:]
    index = 0
    while index < len(rest):
        flag = rest[index]
        if flag in ("--semgrep", "--scc", "--opa", "--conftest"):
            if index + 1 >= len(rest):
                sys.stderr.write(f"missing value for {flag}\n")
                return 1
            raw[flag[2:]] = rest[index + 1]
            index += 2
        else:
            sys.stderr.write(f"unknown argument: {flag}\n")
            return 1

    metrics = {}
    body = []
    status = "ok"
    blocking = False

    try:
        if "semgrep" in raw:
            findings, counts = _parse_semgrep(raw["semgrep"])
            metrics["semgrep_error"] = counts["error"]
            metrics["semgrep_warning"] = counts["warning"]
            metrics["semgrep_info"] = counts["info"]
            metrics["semgrep_findings"] = sum(counts.values())
            body.append(
                {
                    "type": "metric-cards",
                    "title": "Semgrep findings",
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
                    "title": "Findings",
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
            if counts["error"] > 0:
                blocking = True
            elif counts["warning"] > 0:
                status = "warn"

        if "scc" in raw:
            scc = _parse_scc(raw["scc"])
            metrics["loc_code"] = scc["loc_code"]
            metrics["complexity"] = scc["complexity"]
            metrics["files"] = scc["files"]
            body.append(
                {
                    "type": "metric-cards",
                    "title": "Size & complexity",
                    "cards": [
                        {"label": "Lines of code", "value": scc["loc_code"], "delta_metric": "loc_code"},
                        {"label": "Cyclomatic complexity", "value": scc["complexity"], "delta_metric": "complexity"},
                        {"label": "Files", "value": scc["files"], "delta_metric": "files"},
                    ],
                }
            )
            if scc["per_language"]:
                body.append(
                    {
                        "type": "table",
                        "title": "By language",
                        "filterable": True,
                        "columns": [
                            {"key": "language", "label": "Language", "type": "string", "sortable": True},
                            {"key": "files", "label": "Files", "type": "number", "sortable": True},
                            {"key": "code", "label": "Code", "type": "number", "sortable": True},
                            {"key": "complexity", "label": "Complexity", "type": "number", "sortable": True},
                        ],
                        "rows": scc["per_language"],
                        "defaultSort": {"key": "code", "dir": "desc"},
                    }
                )

        policy_rows = []
        policy_failures = 0
        for tool in ("opa", "conftest"):
            if tool in raw:
                fails, rows = _parse_policy(raw[tool], tool)
                policy_failures += fails
                policy_rows.extend(rows)
        if "opa" in raw or "conftest" in raw:
            metrics["policy_failures"] = policy_failures
            body.append(
                {
                    "type": "table",
                    "title": "Policy results",
                    "columns": [
                        {"key": "file", "label": "File", "type": "string", "sortable": True},
                        {"key": "rule", "label": "Rule", "type": "string", "sortable": False},
                    ],
                    "rows": policy_rows,
                }
            )
            if policy_failures > 0:
                blocking = True
    except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as error:
        sys.stderr.write(f"unparseable raw input: {error}\n")
        return 2

    if blocking:
        status = "error"

    fragment = {
        "schema": "dev-report-fragment/v1",
        "id": fragment_id,
        "category": "quality",
        "title": "Code quality & policy",
        "summary": "",
        "status": status,
        "severity": None,
        "producer": {
            "skill": "dev-analysis-quality",
            "tool": "semgrep+scc+opa",
            "version": "1",
        },
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": metrics,
        "body": body,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fragment, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out_path} status={status}")
    return 4 if status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
