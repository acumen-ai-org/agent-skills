#!/usr/bin/env python3
"""Normalize the mission inventory into a dev-report-fragment/v1 fragment.

Usage: to-fragment.py mission <raw.json> <out.fragment.json>

Exit codes:
  0  fragment written; status ok / warn / info
  1  bad arguments
  2  raw inventory unparseable; raw kept for diagnosis
"""
import datetime
import json
import pathlib
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"
PRODUCER = {
    "skill": "dev-analysis-mission",
    "tool": "inventory-mission",
    "version": "1.0.0",
}

REFLECTION_QUESTIONS = [
    "What problem does this product solve, and for whom?",
    "Who is the primary audience, and what do they need from it?",
    "What outcome signals success — what does done look like?",
    "What is explicitly a non-goal — what will this product never do?",
    "How is progress against the mission measured?",
    "For each significant recent change: is it serving a stated goal, or "
    "speculative work without a documented mission link?",
]

NO_DOCS_SUMMARY = "No product mission documentation found"


def _report_help():
    help_path = pathlib.Path(__file__).resolve().parent.parent / "references" / "report-help.md"
    try:
        return help_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _no_docs_body():
    questions = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(REFLECTION_QUESTIONS))
    md = (
        "No product mission documentation was found in this repository "
        "(searched `MISSION.md`, `PRODUCT.md`, `VISION.md`, `docs/vision*`, "
        "`docs/mission*`, `docs/product*`, `docs/strategy*`, `docs/roadmap*`, "
        "OKR / PRD files). Mission alignment cannot be assessed without a "
        "stated mission.\n\n"
        "## Reflection questions\n\n"
        f"{questions}\n\n"
        "Add a `MISSION.md` (see the Skill's "
        "`references/mission-doc-locations.md` template) or point at an "
        "external document via `MISSION_DOC` to make alignment analysis "
        "actionable."
    )
    return [{"type": "markdown", "title": "Mission documentation gap", "md": md}]


def _documented_body(inventory):
    documents = inventory.get("documents", [])

    doc_rows = [
        {
            "path": doc.get("path", ""),
            "words": int(doc.get("word_count", 0)),
            "kind": "thin" if doc.get("thin") else "substantive",
        }
        for doc in documents
    ]
    return [
        {
            "type": "table",
            "title": "Mission documents found",
            "status": "info",
            "columns": [
                {"key": "path", "label": "Path", "type": "string", "sortable": True},
                {"key": "words", "label": "Words", "type": "number", "sortable": True},
                {"key": "kind", "label": "Kind", "type": "string", "sortable": True},
            ],
            "rows": doc_rows,
            "defaultSort": {"key": "words", "dir": "desc"},
        }
    ]


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "mission":
        sys.stderr.write("usage: to-fragment.py mission <raw.json> <out.fragment.json>\n")
        return 1

    raw_path = pathlib.Path(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])

    try:
        inventory = json.loads(raw_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unparseable inventory; see {raw_path}: {error}\n")
        return 2

    raw_metrics = inventory.get("metrics", {})
    mission_docs_found = int(raw_metrics.get("mission_docs_found", 0))
    change_inventory = inventory.get("change_inventory", {})
    changed_areas = change_inventory.get("changed_areas", [])
    changes_total = len(changed_areas)

    generated_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    if mission_docs_found == 0:
        status = "info"
        summary = NO_DOCS_SUMMARY
        body = _no_docs_body()
        changes_mapped = 0
        changes_unmapped = changes_total
        misalignments = 0
    else:
        changes_mapped = 0
        changes_unmapped = changes_total
        misalignments = 0
        if changes_unmapped > 0:
            status = "warn"
            summary = (
                f"{mission_docs_found} mission document(s) found; "
                f"{changes_unmapped} changed area(s) await mapping by the "
                "mission-alignment role"
            )
        else:
            status = "ok"
            summary = (
                f"{mission_docs_found} mission document(s) found; no changed "
                "areas to map"
            )
        body = _documented_body(inventory)

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "mission-alignment",
        "category": "mission",
        "title": "Mission alignment",
        "summary": summary,
        "status": status,
        "producer": PRODUCER,
        "generated_at": generated_at,
        "metrics": {
            "mission_docs_found": mission_docs_found,
            "changes_mapped": changes_mapped,
            "changes_unmapped": changes_unmapped,
            "misalignments": misalignments,
        },
        "body": body,
    }

    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path} status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
