#!/usr/bin/env python3
import json
import pathlib
import sys


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: analysis_gate.py <plan.jsonl> <out_dir>\n")
        return 1
    plan_file = pathlib.Path(sys.argv[1])
    out_dir = pathlib.Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    if plan_file.exists():
        for line in plan_file.read_text().splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    rows = []
    blocking_failures = []
    for e in entries:
        exit_file = out_dir / f"{e['id']}.exit"
        if exit_file.exists():
            try:
                code = int(exit_file.read_text().strip() or "1")
            except ValueError:
                code = 1
            status = "pass" if code == 0 else "fail"
        else:
            code = None
            status = "missing"
        hard = status != "pass" and e.get("blocking") and not e.get("advisory")
        if hard:
            blocking_failures.append(e["id"])
        rows.append({
            "id": e["id"], "group": e["group"], "title": e.get("title", e["id"]),
            "kind": e["kind"], "exit": code, "status": status,
            "blocking": bool(e.get("blocking")), "advisory": bool(e.get("advisory")),
        })

    gate = "fail" if blocking_failures else "pass"
    (out_dir / "_gate.json").write_text(json.dumps(
        {"gate": gate, "blocking": blocking_failures,
         "total": len(rows), "entries": rows}, indent=2) + "\n")

    lines = [f"# Analysis gate: {gate.upper()}", ""]
    if not rows:
        lines.append("No analysis or review tools configured (empty plan).")
    else:
        lines.append("| id | group | kind | status | exit | blocking | advisory |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in rows:
            lines.append(
                f"| {r['id']} | {r['group']} | {r['kind']} | {r['status']} "
                f"| {r['exit']} | {r['blocking']} | {r['advisory']} |")
    if blocking_failures:
        lines += ["", f"Blocking failures: {', '.join(blocking_failures)}"]
    (out_dir / "_summary.md").write_text("\n".join(lines) + "\n")

    sys.stderr.write(f"analysis gate {gate}; {len(rows)} entr{'y' if len(rows)==1 else 'ies'}\n")
    return 3 if blocking_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
