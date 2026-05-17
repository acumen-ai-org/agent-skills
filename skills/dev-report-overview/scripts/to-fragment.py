#!/usr/bin/env python3
"""Emit the pinned overview fragment (dev-report-fragment/v1, category overview).

Usage:
  to-fragment.py <bullets.md> <image> <scope.json> <out.fragment.json>

  <bullets.md>  the high-level scope bullets (markdown), from the
                overview-synthesis role.
  <image>       the infographic: a PNG file path (base64-encoded into a
                data: URI here) or an existing data:image/...;base64,... URI
                (passed through), or the literal NO-IMAGE (no image body).
  <scope.json>  the rollup the orchestrator built from the staged fragment
                set: at least { "metrics": {string: number},
                "summary": str }; optional "title", "status", "image_alt",
                "image_title".
  <out.fragment.json>  where the contract fragment is written; its parent
                directory must be the same staging dir dev-report-build
                consumes so the build pins it first.

Exit codes:
  0  fragment written
  1  bad arguments
  2  an input was unreadable / unparseable (inputs kept for diagnosis)
"""
import base64
import datetime
import json
import pathlib
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"
PRODUCER = {
    "skill": "dev-report-overview",
    "tool": "to-fragment",
    "version": "1.0.0",
}
STATUSES = {"ok", "info", "warn", "error"}
DEFAULT_ALT = "Release overview infographic"


def _data_uri(image_arg):
    if image_arg == "NO-IMAGE":
        return None
    if image_arg.startswith("data:image/"):
        return image_arg
    png_path = pathlib.Path(image_arg)
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def main():
    if len(sys.argv) != 5:
        sys.stderr.write(
            "usage: to-fragment.py <bullets.md> <image> <scope.json> "
            "<out.fragment.json>\n"
        )
        return 1

    bullets_path = pathlib.Path(sys.argv[1])
    image_arg = sys.argv[2]
    scope_path = pathlib.Path(sys.argv[3])
    out_path = pathlib.Path(sys.argv[4])

    try:
        bullets_md = bullets_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        sys.stderr.write(f"unreadable bullets; see {bullets_path}: {error}\n")
        return 2
    if not bullets_md:
        sys.stderr.write(f"empty bullets file: {bullets_path}\n")
        return 2

    try:
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unparseable scope; see {scope_path}: {error}\n")
        return 2
    if not isinstance(scope, dict):
        sys.stderr.write(f"scope must be a JSON object: {scope_path}\n")
        return 2

    try:
        src = _data_uri(image_arg)
    except OSError as error:
        sys.stderr.write(f"unreadable image; see {image_arg}: {error}\n")
        return 2

    raw_metrics = scope.get("metrics", {})
    if not isinstance(raw_metrics, dict):
        sys.stderr.write("scope.metrics must be an object\n")
        return 2
    metrics = {}
    for key, value in raw_metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            sys.stderr.write(f"scope.metrics.{key} must be a number\n")
            return 2
        metrics[str(key)] = value

    summary = scope.get("summary", "")
    if not isinstance(summary, str):
        sys.stderr.write("scope.summary must be a string\n")
        return 2

    status = scope.get("status", "info")
    if status not in STATUSES:
        sys.stderr.write("scope.status must be ok | info | warn | error\n")
        return 2

    title = scope.get("title") or "Release overview"

    generated_at = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    body = []
    if src is not None:
        image_section = {
            "type": "image",
            "title": "Overview",
            "src": src,
            "alt": scope.get("image_alt") or DEFAULT_ALT,
        }
        image_title = scope.get("image_title")
        if isinstance(image_title, str) and image_title:
            image_section["title"] = image_title
        body.append(image_section)
    body.append(
        {"type": "markdown", "title": "Release scope", "md": bullets_md}
    )

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "overview",
        "category": "overview",
        "title": title,
        "summary": summary,
        "status": status,
        "producer": PRODUCER,
        "generated_at": generated_at,
        "metrics": metrics,
        "body": body,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path} status={status} image={'yes' if src else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
