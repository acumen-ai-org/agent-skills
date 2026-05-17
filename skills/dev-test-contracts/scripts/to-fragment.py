#!/usr/bin/env python3
"""Normalize a pact provider-verification result into a report fragment.

Usage: to-fragment.py <id> <raw-result.json> <out-fragment.json>

Emits exactly one dev-report-fragment/v1 object in category "contracts".
`status` is the verification verdict: "error" if any interaction failed,
"warn" if every interaction passed but at least one carried no provider
state, otherwise "ok". Every interaction is enumerated in a table body.

Exit codes:
  0  fragment written; status ok/warn
  1  bad arguments
  2  raw result unparseable; nothing written
  4  fragment written; status error (a failed interaction)
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = "dev-report-fragment/v1"
FAILURE_STATUSES = {"failed", "failure", "error"}
SUCCESS_STATUSES = {"passed", "success", "ok", "successful"}


def collect_interactions(node):
    found = []
    if isinstance(node, dict):
        for key in ("examples", "interactions", "verificationResults", "results"):
            value = node.get(key)
            if isinstance(value, list):
                found.extend(value)
        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(collect_interactions(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect_interactions(item))
    return found


def interaction_verdict(item):
    status = str(item.get("status", item.get("status_text", ""))).strip().lower()
    if status in FAILURE_STATUSES:
        return "failed"
    if item.get("success") is False:
        return "failed"
    if item.get("mismatches"):
        return "failed"
    if item.get("exception"):
        return "failed"
    if status in SUCCESS_STATUSES:
        return "passed"
    if item.get("success") is True:
        return "passed"
    if item.get("pending") is True:
        return "passed"
    return "passed"


def interaction_consumer(item):
    consumer = item.get("consumer")
    if isinstance(consumer, dict):
        return str(consumer.get("name", "") or "")
    if isinstance(consumer, str):
        return consumer
    return str(item.get("consumerName", "") or "")


def interaction_provider_state(item):
    for key in ("providerState", "provider_state", "providerStates", "provider_states"):
        value = item.get(key)
        if isinstance(value, list):
            names = [
                str(entry.get("name", entry) if isinstance(entry, dict) else entry)
                for entry in value
                if entry
            ]
            if names:
                return "; ".join(names)
        elif isinstance(value, str) and value.strip():
            return value.strip()
        elif isinstance(value, dict):
            name = value.get("name")
            if name:
                return str(name)
    return ""


def interaction_description(item):
    for key in ("description", "interactionDescription", "name", "request"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            method = value.get("method")
            path = value.get("path")
            if method or path:
                return f"{method or ''} {path or ''}".strip()
    return "(unnamed interaction)"


def interaction_detail(item):
    mismatches = item.get("mismatches")
    if isinstance(mismatches, list) and mismatches:
        parts = []
        for mismatch in mismatches:
            if isinstance(mismatch, dict):
                parts.append(
                    str(mismatch.get("description")
                        or mismatch.get("mismatch")
                        or mismatch.get("type")
                        or mismatch)
                )
            else:
                parts.append(str(mismatch))
        return " | ".join(parts)
    exception = item.get("exception")
    if isinstance(exception, dict):
        return str(exception.get("message", exception))
    if isinstance(exception, str) and exception.strip():
        return exception.strip()
    return ""


def main():
    if len(sys.argv) != 4:
        sys.stderr.write("usage: to-fragment.py <id> <raw-result.json> <out-fragment.json>\n")
        return 1

    fragment_id = sys.argv[1]
    raw_path = pathlib.Path(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])

    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unreadable / invalid pact result: {error}\n")
        return 2

    interactions = collect_interactions(raw)

    rows = []
    failed = 0
    passed = 0
    stateless = 0
    for item in interactions:
        if not isinstance(item, dict):
            continue
        verdict = interaction_verdict(item)
        provider_state = interaction_provider_state(item)
        if not provider_state:
            stateless += 1
        if verdict == "failed":
            failed += 1
        else:
            passed += 1
        rows.append(
            {
                "consumer": interaction_consumer(item) or "(unknown)",
                "interaction": interaction_description(item),
                "provider_state": provider_state or "(none)",
                "result": verdict,
                "detail": interaction_detail(item),
            }
        )

    total = len(rows)
    if failed > 0:
        status = "error"
    elif stateless > 0:
        status = "warn"
    else:
        status = "ok"

    if total == 0:
        status = "warn"
        summary = "No consumer interactions were verified."
    else:
        summary = (
            f"{total} interaction(s) verified: {passed} passed, {failed} failed; "
            f"{stateless} without a provider state."
        )

    severity = None
    if status == "error":
        severity = min(100, 50 + failed * 10)
    elif status == "warn":
        severity = 20

    body = [
        {
            "type": "metric-cards",
            "cards": [
                {"label": "Interactions", "value": total, "delta_metric": "interactions"},
                {"label": "Passed", "value": passed, "delta_metric": "passed"},
                {"label": "Failed", "value": failed, "delta_metric": "failed"},
                {
                    "label": "No provider state",
                    "value": stateless,
                    "delta_metric": "without_provider_state",
                },
            ],
        },
        {
            "type": "table",
            "title": "Verified interactions",
            "filterable": True,
            "columns": [
                {"key": "consumer", "label": "Consumer", "type": "string", "sortable": True},
                {"key": "interaction", "label": "Interaction", "type": "string", "sortable": True},
                {"key": "provider_state", "label": "Provider state", "type": "string", "sortable": True},
                {"key": "result", "label": "Result", "type": "string", "sortable": True},
                {"key": "detail", "label": "Detail", "type": "string", "sortable": False},
            ],
            "rows": rows
            or [
                {
                    "consumer": "(none)",
                    "interaction": "(no interactions verified)",
                    "provider_state": "(none)",
                    "result": "n/a",
                    "detail": "",
                }
            ],
            "defaultSort": {"key": "result", "dir": "desc"},
        },
    ]

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": fragment_id,
        "category": "contracts",
        "title": "Consumer contract verification",
        "summary": summary,
        "status": status,
        "severity": severity,
        "producer": {
            "skill": "dev-test-contracts",
            "tool": "pact",
            "version": "provider-verification",
        },
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "interactions": total,
            "passed": passed,
            "failed": failed,
            "without_provider_state": stateless,
        },
        "body": body,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} status={status}")
    return 4 if status == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
