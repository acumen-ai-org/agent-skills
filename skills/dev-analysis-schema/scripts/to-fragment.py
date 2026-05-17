#!/usr/bin/env python3
import datetime
import json
import pathlib
import sys

USAGE = "usage: to-fragment.py schema <schema-diff.json> <out_fragment.json>\n"

OASDIFF_VERSION = "1.10.27"
GRAPHQL_INSPECTOR_VERSION = "5.0.0"


def now_iso():
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def oasdiff_change_row(change, visibility):
    if not isinstance(change, dict):
        return {
            "surface": "OpenAPI",
            "visibility": visibility,
            "criticality": "BREAKING",
            "location": "",
            "detail": str(change),
        }
    location = (
        change.get("operationId")
        or change.get("path")
        or change.get("operation")
        or ""
    )
    detail = (
        change.get("text")
        or change.get("description")
        or change.get("id")
        or change.get("kind")
        or ""
    )
    return {
        "surface": "OpenAPI",
        "visibility": visibility,
        "criticality": "BREAKING",
        "location": str(location),
        "detail": str(detail),
    }


def graphql_change_row(change):
    criticality = str(change.get("criticality", "")).upper() or "SAFE"
    return {
        "surface": "GraphQL",
        "visibility": "public",
        "criticality": criticality,
        "location": str(change.get("path", "")),
        "detail": str(change.get("message", change.get("type", ""))),
    }


def mcp_change_row(change):
    return {
        "surface": "MCP",
        "visibility": "public",
        "criticality": str(change.get("criticality", "SAFE")).upper(),
        "location": str(change.get("schema", "")),
        "detail": "{}: {}".format(
            change.get("kind", ""), change.get("detail", "")
        ),
    }


def build_rows(diff):
    rows = []
    openapi = diff.get("openapi", {})
    for change in openapi.get("public", []):
        rows.append(oasdiff_change_row(change, "public"))
    for change in openapi.get("private", []):
        rows.append(oasdiff_change_row(change, "private"))
    for change in diff.get("graphql", []):
        if isinstance(change, dict):
            rows.append(graphql_change_row(change))
    for change in diff.get("mcp", []):
        if isinstance(change, dict):
            rows.append(mcp_change_row(change))
    return rows


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "schema":
        sys.stderr.write(USAGE)
        return 1

    raw_path = pathlib.Path(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])

    try:
        diff = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"unreadable / invalid schema diff: {error}\n")
        return 2

    summary = diff.get("summary", {})
    has_diff = bool(summary.get("hasDiff"))
    public_breaking = int(summary.get("publicBreaking", 0))
    private_breaking = int(summary.get("privateBreaking", 0))
    total_changes = int(summary.get("totalChanges", 0))
    tool_missing = bool(diff.get("toolMissing"))

    if not has_diff:
        status = "ok"
        provisional_summary = "No API or schema changes between the two refs."
        exit_code = 0
    elif public_breaking > 0:
        status = "error"
        provisional_summary = (
            f"{public_breaking} public breaking change(s); "
            f"{total_changes} change(s) total."
        )
        exit_code = 4
    elif private_breaking > 0:
        status = "warn"
        provisional_summary = (
            f"{private_breaking} private-only breaking change(s); "
            f"no public breaking change."
        )
        exit_code = 0
    else:
        status = "warn"
        provisional_summary = (
            f"{total_changes} non-breaking schema change(s)."
        )
        exit_code = 0

    rows = build_rows(diff)

    body = [
        {
            "type": "metric-cards",
            "cards": [
                {
                    "label": "Has diff",
                    "value": 1 if has_diff else 0,
                    "delta_metric": "hasDiff",
                },
                {
                    "label": "Public breaking",
                    "value": public_breaking,
                    "delta_metric": "publicBreaking",
                },
                {
                    "label": "Private breaking",
                    "value": private_breaking,
                    "delta_metric": "privateBreaking",
                },
                {
                    "label": "Total changes",
                    "value": total_changes,
                    "delta_metric": "totalChanges",
                },
            ],
        }
    ]

    if rows:
        body.append(
            {
                "type": "table",
                "title": "Schema changes",
                "filterable": True,
                "columns": [
                    {"key": "surface", "label": "Surface", "type": "string", "sortable": True},
                    {"key": "visibility", "label": "Visibility", "type": "string", "sortable": True},
                    {"key": "criticality", "label": "Criticality", "type": "string", "sortable": True},
                    {"key": "location", "label": "Location", "type": "string", "sortable": True},
                    {"key": "detail", "label": "Detail", "type": "string", "sortable": False},
                ],
                "rows": rows,
                "defaultSort": {"key": "criticality", "dir": "asc"},
            }
        )

    if tool_missing:
        body.append(
            {
                "type": "markdown",
                "title": "Tooling note",
                "md": (
                    "One or more diff engines were unavailable "
                    "(Docker/Node missing). Coverage is partial; "
                    "re-run with the engines installed for a complete diff."
                ),
            }
        )

    fragment = {
        "schema": "dev-report-fragment/v1",
        "id": "schema-diff",
        "category": "schema",
        "title": "API & schema surface diff",
        "summary": provisional_summary,
        "status": status,
        "producer": {
            "skill": "dev-analysis-schema",
            "tool": f"oasdiff/{OASDIFF_VERSION}+graphql-inspector/{GRAPHQL_INSPECTOR_VERSION}+mcp-schema-diff",
            "version": "1",
        },
        "generated_at": now_iso(),
        "metrics": {
            "hasDiff": 1 if has_diff else 0,
            "publicBreaking": public_breaking,
            "privateBreaking": private_breaking,
            "totalChanges": total_changes,
        },
        "body": body,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(
        "FRAGMENT schema-diff status={} hasDiff={} exit={}".format(
            status, 1 if has_diff else 0, exit_code
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
