#!/usr/bin/env python3
import json
import sys

EXT = {"text": "txt", "markdown": "md", "html": "html", "json": "json", "sarif": "sarif"}


def main():
    try:
        cfg = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"analysis_plan: invalid resolved config on stdin: {exc}\n")
        return 2
    for group in ("analysis", "review"):
        for entry in cfg.get(group, []):
            if not entry.get("enabled", True):
                continue
            fmt = entry.get("report", {}).get("format", "markdown")
            sys.stdout.write(json.dumps({
                "group": group,
                "id": entry["id"],
                "title": entry.get("title", entry["id"]),
                "kind": entry["kind"],
                "run": entry.get("run"),
                "args": entry.get("args", {}),
                "heavy": bool(entry.get("heavy", entry["kind"] == "skill")),
                "blocking": bool(entry.get("blocking", False)),
                "advisory": bool(entry.get("advisory", False)),
                "timeoutSeconds": int(entry.get("timeoutSeconds", 1800)),
                "format": fmt,
                "report": f"{entry['id']}.{EXT.get(fmt, 'txt')}",
            }))
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
