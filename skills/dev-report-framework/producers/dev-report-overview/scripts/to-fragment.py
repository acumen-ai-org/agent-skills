#!/usr/bin/env python3
"""Emit the pinned overview fragment (dev-report-fragment/v1, category overview).

Usage:
  to-fragment.py <bullets.md> <image> <scope.json> <out.fragment.json>
  to-fragment.py <bullets.md> <image> <scope.json> <out.fragment.json> \
      <overview-extras.json>

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
  <overview-extras.json>  optional; the merged classify-changes + role output
                (diff_view / changes / shifts / images). Absent ⇒ the fragment
                is byte-identical to the four-argument form.

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
HERO_MENUS = {
    "summary": "Summary",
    "diff-view": "Diff view",
    "changes": "Changes",
    "shifts": "Shifts",
}


def _report_help():
    help_path = (
        pathlib.Path(__file__).resolve().parent
        / ".."
        / "references"
        / "report-help.md"
    )
    try:
        return help_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _data_uri(image_arg):
    if image_arg == "NO-IMAGE":
        return None
    if image_arg.startswith("data:image/"):
        return image_arg
    png_path = pathlib.Path(image_arg)
    encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _hero_src(value):
    if not isinstance(value, str) or not value:
        return None
    if value == "NO-IMAGE":
        return None
    if value.startswith("data:image/"):
        return value
    try:
        encoded = base64.b64encode(
            pathlib.Path(value).read_bytes()
        ).decode("ascii")
    except OSError:
        return None
    return f"data:image/png;base64,{encoded}"


def _diff_view_section(diff_view):
    if not isinstance(diff_view, dict):
        return None, "extras.diff_view must be an object"
    raw = diff_view.get("perspectives", [])
    if not isinstance(raw, list):
        return None, "extras.diff_view.perspectives must be an array"
    kept = []
    for perspective in raw:
        if not isinstance(perspective, dict):
            return None, "extras.diff_view.perspectives[] must be objects"
        items = perspective.get("items", [])
        if not isinstance(items, list):
            return None, "extras.diff_view perspective items must be an array"
        clean = []
        for item in items:
            if not isinstance(item, dict):
                return None, "extras.diff_view item must be an object"
            before = item.get("before", "")
            after = item.get("after", "")
            if not isinstance(before, str) or not isinstance(after, str):
                return None, "extras.diff_view item before/after must be strings"
            if before == "" and after == "":
                return None, "extras.diff_view item cannot have both empty"
            clean.append({"before": before, "after": after})
        if not clean:
            continue
        slug = perspective.get("slug", "")
        title = perspective.get("title", "")
        lead = perspective.get("lead", "")
        if not isinstance(slug, str) or not slug:
            return None, "extras.diff_view perspective needs a slug"
        if not isinstance(title, str) or not title:
            return None, "extras.diff_view perspective needs a title"
        if not isinstance(lead, str) or not lead:
            return None, "extras.diff_view perspective needs a lead"
        kept.append(
            {"slug": slug, "title": title, "lead": lead, "items": clean}
        )
    if not kept:
        return None, None
    return {
        "type": "diff-view",
        "title": "Diff view",
        "menu": "Diff view",
        "perspectives": kept,
    }, None


def _changes_section(changes):
    if not isinstance(changes, dict):
        return None, "extras.changes must be an object"
    groups = changes.get("groups", [])
    if not isinstance(groups, list):
        return None, "extras.changes.groups must be an array"
    lines = []
    for group in groups:
        if not isinstance(group, dict):
            return None, "extras.changes.groups[] must be objects"
        gtype = group.get("type", "")
        if not isinstance(gtype, str) or not gtype:
            return None, "extras.changes group needs a type"
        count = group.get("count", 0)
        if isinstance(count, bool) or not isinstance(count, int):
            return None, "extras.changes group count must be an integer"
        bullets = group.get("bullets", [])
        if not isinstance(bullets, list):
            return None, "extras.changes group bullets must be an array"
        lines.append(f"### {gtype} ({count})")
        for bullet in bullets:
            if not isinstance(bullet, str):
                return None, "extras.changes group bullet must be a string"
            lines.append(f"- {bullet}")
        lines.append("")
    if not lines:
        return None, None
    return {
        "type": "markdown",
        "title": "Features, fixes & other changes",
        "menu": "Changes",
        "md": "\n".join(lines).strip(),
    }, None


def _shifts_section(shifts):
    if not isinstance(shifts, dict):
        return None, "extras.shifts must be an object"
    rows = shifts.get("rows", [])
    if not isinstance(rows, list):
        return None, "extras.shifts.rows must be an array"
    lines = []
    breaking = False
    for row in rows:
        if not isinstance(row, dict):
            return None, "extras.shifts.rows[] must be objects"
        shift = row.get("shift", "")
        signal = row.get("signal", "")
        if not isinstance(shift, str) or not shift:
            return None, "extras.shifts row needs a shift"
        if not isinstance(signal, str):
            return None, "extras.shifts row signal must be a string"
        modules = row.get("modules", [])
        if not isinstance(modules, list) or any(
            not isinstance(m, str) for m in modules
        ):
            return None, "extras.shifts row modules must be a string array"
        lowered = (shift + " " + signal).lower()
        if (
            "breaking" in lowered
            or "security" in lowered
            or "public-api" in lowered
            or "public api" in lowered
        ):
            breaking = True
        scope = ", ".join(modules) if modules else "root"
        lines.append(f"- **{shift}** — {signal} ({scope})")
    if not lines:
        return None, None
    return {
        "type": "markdown",
        "title": "Architectural & technical shifts",
        "menu": "Shifts",
        "status": "warn" if breaking else "info",
        "md": "\n".join(lines),
    }, None


def _hero_section(slug, value):
    src = _hero_src(value)
    if src is None:
        return None
    return {
        "type": "image",
        "title": HERO_MENUS[slug],
        "menu": HERO_MENUS[slug],
        "src": src,
        "alt": f"{HERO_MENUS[slug]} hero illustration",
    }


def _build_extra_sections(extras, image_section, scope_section):
    images = extras.get("images", {})
    if images is None:
        images = {}
    if not isinstance(images, dict):
        return None, "extras.images must be an object"

    if image_section is not None:
        image_section["menu"] = "Summary"
    scope_section["menu"] = "Summary"

    appended = []
    diff_section, err = _diff_view_section(extras.get("diff_view", {}))
    if err is not None:
        return None, err
    changes_section, err = _changes_section(extras.get("changes", {}))
    if err is not None:
        return None, err
    shifts_section, err = _shifts_section(extras.get("shifts", {}))
    if err is not None:
        return None, err

    plan = [
        ("diff-view", diff_section),
        ("changes", changes_section),
        ("shifts", shifts_section),
    ]
    for slug, section in plan:
        if section is None:
            continue
        hero = _hero_section(slug, images.get(slug))
        if hero is not None:
            appended.append(hero)
        appended.append(section)
    return appended, None


def main():
    if len(sys.argv) not in (5, 6):
        sys.stderr.write(
            "usage: to-fragment.py <bullets.md> <image> <scope.json> "
            "<out.fragment.json> [<overview-extras.json>]\n"
        )
        return 1

    bullets_path = pathlib.Path(sys.argv[1])
    image_arg = sys.argv[2]
    scope_path = pathlib.Path(sys.argv[3])
    out_path = pathlib.Path(sys.argv[4])
    extras_path = pathlib.Path(sys.argv[5]) if len(sys.argv) == 6 else None

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

    extras = None
    if extras_path is not None:
        try:
            extras = json.loads(extras_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            sys.stderr.write(
                f"unparseable extras; see {extras_path}: {error}\n"
            )
            return 2
        if not isinstance(extras, dict):
            sys.stderr.write(f"extras must be a JSON object: {extras_path}\n")
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
    image_section = None
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
    scope_section = {
        "type": "markdown",
        "title": "Release scope",
        "md": bullets_md,
    }
    body.append(scope_section)

    if extras is not None:
        appended, err = _build_extra_sections(
            extras, image_section, scope_section
        )
        if err is not None:
            sys.stderr.write(f"malformed extras: {err}\n")
            return 2
        body.extend(appended)

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
    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path} status={status} image={'yes' if src else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
