#!/usr/bin/env python3
"""Emit the report-status fragment (dev-report-fragment/v1, category report).

Usage: to-fragment.py <build-status.json> <out-dir>

<build-status.json> is the orchestrator's per-producer outcome roll-up:

  {
    "schema": "dev-report-build-status/v1",
    "release": "<id>",
    "generated_at": "<ISO-8601>",
    "producers": [
      {"skill": str, "fragment_id": str,
       "status": "ok" | "failed" | "skipped",
       "exit_code": int, "message": str},
      ...
    ]
  }

Writes one fragment to <out-dir>/report-status.fragment.json. The fragment
`status` is the worst producer outcome: error if any failed, else warn if any
skipped, else ok.

Exit codes:
  0  fragment written
  1  bad arguments
  2  input unreadable / unparseable / wrong schema (nothing written)
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = "dev-report-fragment/v1"
INPUT_SCHEMA = "dev-report-build-status/v1"
PRODUCER = {
    "skill": "dev-report-status",
    "tool": "to-fragment",
    "version": "1.0.0",
}
PRODUCER_STATUSES = {"ok", "failed", "skipped"}


def _report_help():
    help_path = pathlib.Path(__file__).resolve().parent / ".." / "references" / "report-help.md"
    try:
        return help_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: to-fragment.py <build-status.json> <out-dir>\n")
        return 1

    in_path = pathlib.Path(sys.argv[1])
    out_dir = pathlib.Path(sys.argv[2])

    try:
        data = json.loads(in_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unreadable / invalid build-status: {error}\n")
        return 2

    if not isinstance(data, dict) or data.get("schema") != INPUT_SCHEMA:
        sys.stderr.write(f"build-status must be a JSON object with schema '{INPUT_SCHEMA}'\n")
        return 2

    producers = data.get("producers")
    if not isinstance(producers, list):
        sys.stderr.write("build-status.producers must be an array\n")
        return 2

    release = data.get("release")
    if not isinstance(release, str) or not release:
        release = "(unknown)"

    rows = []
    ok = 0
    failed = 0
    skipped = 0
    for entry in producers:
        if not isinstance(entry, dict):
            sys.stderr.write("build-status.producers entries must be objects\n")
            return 2
        producer_status = str(entry.get("status", "")).strip().lower()
        if producer_status not in PRODUCER_STATUSES:
            sys.stderr.write(
                "build-status producer status must be ok | failed | skipped\n"
            )
            return 2
        if producer_status == "ok":
            ok += 1
            row_status = "ok"
        elif producer_status == "failed":
            failed += 1
            row_status = "error"
        else:
            skipped += 1
            row_status = "warn"
        exit_code = entry.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            exit_code = -1
        rows.append(
            {
                "skill": str(entry.get("skill", "") or "(unknown)"),
                "fragment_id": str(entry.get("fragment_id", "") or "(none)"),
                "status": producer_status,
                "exit_code": exit_code,
                "message": str(entry.get("message", "") or ""),
                "_row_status": row_status,
            }
        )

    total = len(rows)
    if failed > 0:
        status = "error"
    elif skipped > 0:
        status = "warn"
    else:
        status = "ok"

    if total == 0:
        summary = "No report producers ran."
    else:
        summary = (
            f"{total} report producer(s): {ok} ok, {failed} failed, "
            f"{skipped} skipped."
        )

    generated_at = (
        data.get("generated_at")
        if isinstance(data.get("generated_at"), str) and data.get("generated_at")
        else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "skill": row["skill"],
                "fragment_id": row["fragment_id"],
                "status": row["status"],
                "exit_code": row["exit_code"],
                "message": row["message"],
            }
        )

    body = [
        {
            "type": "metric-cards",
            "cards": [
                {"label": "Producers", "value": total},
                {"label": "OK", "value": ok},
                {"label": "Failed", "value": failed},
                {"label": "Skipped", "value": skipped},
            ],
        },
        {
            "type": "table",
            "title": "Producer build status",
            "status": status,
            "view": "release",
            "filterable": True,
            "columns": [
                {"key": "skill", "label": "Skill", "type": "string", "sortable": True},
                {"key": "fragment_id", "label": "Fragment", "type": "string", "sortable": True},
                {"key": "status", "label": "Status", "type": "string", "sortable": True},
                {"key": "exit_code", "label": "Exit", "type": "number", "sortable": True},
                {"key": "message", "label": "Message", "type": "string", "sortable": False},
            ],
            "rows": table_rows
            or [
                {
                    "skill": "(none)",
                    "fragment_id": "(none)",
                    "status": "n/a",
                    "exit_code": -1,
                    "message": "no producers ran",
                }
            ],
            "defaultSort": {"key": "status", "dir": "desc"},
        },
    ]

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "report-status",
        "category": "report",
        "title": "Report build status",
        "summary": summary,
        "status": status,
        "producer": PRODUCER,
        "generated_at": generated_at,
        "metrics": {
            "producers": total,
            "ok": ok,
            "failed": failed,
            "skipped": skipped,
        },
        "body": body,
    }

    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report-status.fragment.json"
    out_path.write_text(
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path} status={status} release={release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
