#!/usr/bin/env python3
"""Emit the release-diff fragment (dev-report-fragment/v1, category report).

Usage: to-fragment.py <diff-facts.json> <perspectives.json> <out-dir>

<diff-facts.json> is collect-diff.sh's merged static facts (carries
`repo`, `range`, `ref_a`, `ref_b`). <perspectives.json> is assembled by the
producer from the synthesis role + content-to-image outputs:

  {
    "perspectives": [
      {"slug": str, "name": str,
       "status": "ok" | "info" | "warn" | "error",
       "narrative": str,
       "image": str | null}
    ]
  }

Writes one fragment to <out-dir>/release-diff.fragment.json. One menu group
per perspective (an image section when a PNG exists, plus the narrative
markdown), then a closing risk-summary section. The fragment `status` is the
worst perspective status. Every section is left-column (untagged `view`).

Exit codes:
  0  fragment written
  1  bad arguments
  2  input unreadable / unparseable / wrong shape (nothing written)
"""
import json
import pathlib
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = "dev-report-fragment/v1"
PRODUCER = {
    "skill": "dev-report-release-diff",
    "tool": "to-fragment",
    "version": "1.0.0",
}
STATUSES = ("ok", "info", "warn", "error")
RANK = {"ok": 0, "info": 1, "warn": 2, "error": 3}
HEADLINE = {
    "error": "Blocking findings",
    "warn": "Review required",
    "info": "No blocking findings",
    "ok": "No blocking findings",
}


def _report_help():
    help_path = pathlib.Path(__file__).resolve().parent / ".." / "references" / "report-help.md"
    try:
        return help_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def main():
    if len(sys.argv) != 4:
        sys.stderr.write("usage: to-fragment.py <diff-facts.json> <perspectives.json> <out-dir>\n")
        return 1

    facts_path = pathlib.Path(sys.argv[1])
    persp_path = pathlib.Path(sys.argv[2])
    out_dir = pathlib.Path(sys.argv[3])

    try:
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        persp_doc = json.loads(persp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unreadable / invalid input: {error}\n")
        return 2

    if not isinstance(facts, dict) or not isinstance(persp_doc, dict):
        sys.stderr.write("both inputs must be JSON objects\n")
        return 2

    perspectives = persp_doc.get("perspectives")
    if not isinstance(perspectives, list):
        sys.stderr.write("perspectives.perspectives must be an array\n")
        return 2

    ref_a = str(facts.get("ref_a", "") or "?")
    ref_b = str(facts.get("ref_b", "") or "?")
    rng = str(facts.get("range", "") or f"{ref_a}..{ref_b}")

    counts = {"ok": 0, "info": 0, "warn": 0, "error": 0}
    body = []
    risk_rows = []
    for entry in perspectives:
        if not isinstance(entry, dict):
            sys.stderr.write("each perspective must be an object\n")
            return 2
        name = str(entry.get("name", "") or "").strip()
        narrative = str(entry.get("narrative", "") or "").strip()
        if not name or not narrative:
            sys.stderr.write("each perspective needs a non-empty name and narrative\n")
            return 2
        p_status = str(entry.get("status", "") or "").strip().lower()
        if p_status not in STATUSES:
            p_status = "info"
        counts[p_status] += 1
        image = entry.get("image")
        if isinstance(image, str) and image.strip():
            body.append(
                {
                    "type": "image",
                    "title": name,
                    "status": p_status,
                    "menu": name,
                    "src": image.strip(),
                    "alt": name,
                }
            )
            body.append(
                {
                    "type": "markdown",
                    "status": p_status,
                    "menu": name,
                    "md": narrative,
                }
            )
        else:
            body.append(
                {
                    "type": "markdown",
                    "title": name,
                    "status": p_status,
                    "menu": name,
                    "md": narrative,
                }
            )
        risk_rows.append(f"| {name} | {p_status} |")

    total = len(perspectives)
    worst = "ok"
    for status in STATUSES:
        if counts[status] and RANK[status] > RANK[worst]:
            worst = status
    if total == 0:
        worst = "info"

    if total == 0:
        summary = f"No perspectives admitted for {rng}."
        body = [
            {
                "type": "markdown",
                "title": "Release diff",
                "md": f"No perspective had a static fact source for `{rng}`.",
            }
        ]
    else:
        summary = (
            f"{total} perspective(s) across {ref_a} → {ref_b}; "
            f"worst status: {worst}."
        )
        risk_table = "\n".join(
            ["| Perspective | Status |", "| --- | --- |"] + risk_rows
        )
        body.append(
            {
                "type": "markdown",
                "title": "Release risk summary",
                "status": worst,
                "menu": "Risk summary",
                "md": f"{risk_table}\n\n**{HEADLINE[worst]}** across {total} perspective(s).",
            }
        )

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "release-diff",
        "category": "report",
        "title": "Release diff",
        "summary": summary,
        "status": worst,
        "producer": PRODUCER,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "perspectives": total,
            "ok": counts["ok"],
            "info": counts["info"],
            "warn": counts["warn"],
            "error": counts["error"],
        },
        "body": body,
    }

    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "release-diff.fragment.json"
        out_path.write_text(
            json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        sys.stderr.write(f"cannot write fragment: {error}\n")
        return 2

    print(f"wrote {out_path} status={worst} perspectives={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
