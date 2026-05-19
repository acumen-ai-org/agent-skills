#!/usr/bin/env python3
"""Backfill the vs-production column of staged fragments lacking one.

Usage:
  backfill.py plan  <staging-dir> <reports-root>
  backfill.py apply <fragment-path> <summary-file> <image-data-uri-file>

plan
  Reads <reports-root>/releases.json (newest-first) and resolves the previous
  release (releases[0]). For every staged *.json fragment in <staging-dir> that
  has ZERO view:"production" sections AND has a prior same-id fragment at
  <reports-root>/<prev.path or prev.id>/data/<category>/<id>.json, prints one
  tab-separated line:

    <fragment-path>\t<prev-fragment-path>

  Fragments that already carry a view:"production" section, and fragments with
  no prior same-id counterpart (new this release, or no prior report at all),
  are skipped. No reports-root / no releases.json / no prior release => nothing
  is printed and the exit is 0 (the vs-production column stays empty, exactly
  today's behavior).

apply
  Appends to <fragment-path>'s body[], in order, a
  { "type":"markdown", "view":"production", "status":"info",
    "title":"vs production", "md": <summary-file contents> } section then a
  { "type":"image", "view":"production", "src": <image-data-uri-file
    contents>, "alt":"vs production summary" } section, and rewrites the
  fragment. The markdown section is status info (commentary on the delta); the
  image section omits status. Existing sections are not touched; no menu is
  added. A fragment-level help string is added only when the fragment carries
  none, so a producer's own help is never clobbered. This script never calls an
  LLM and never generates an image — the role writes the summary,
  content-to-image's text-to-image.sh writes the image; revalidate with
  dev-report-framework/scripts/validate_fragments.py after apply.

Exit codes:
  0  ok (plan printed its lines, possibly none; apply rewrote the fragment)
  1  bad arguments
  2  an input was unreadable / unparseable JSON (nothing written)
  5  staging-dir or reports-root is not a usable directory
"""
import json
import pathlib
import sys


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


def _load_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _has_production_view(fragment):
    body = fragment.get("body")
    if not isinstance(body, list):
        return False
    for section in body:
        if isinstance(section, dict) and section.get("view") == "production":
            return True
    return False


def _previous_release(reports_root):
    releases_path = reports_root / "releases.json"
    if not releases_path.is_file():
        return None
    try:
        doc = _load_json(releases_path)
    except (json.JSONDecodeError, OSError):
        return None
    releases = doc.get("releases") if isinstance(doc, dict) else None
    if not isinstance(releases, list) or not releases:
        return None
    first = releases[0]
    if not isinstance(first, dict):
        return None
    return first


def _release_dir(reports_root, release):
    path = release.get("path") or release.get("id")
    if not isinstance(path, str) or not path:
        return None
    return reports_root / path.rstrip("/")


def _plan(staging_dir, reports_root):
    staging_dir = pathlib.Path(staging_dir)
    reports_root = pathlib.Path(reports_root)
    if not staging_dir.is_dir():
        sys.stderr.write(f"staging-dir is not a directory: {staging_dir}\n")
        return 5

    if not reports_root.is_dir():
        return 0
    previous = _previous_release(reports_root)
    if previous is None:
        return 0
    prev_dir = _release_dir(reports_root, previous)
    if prev_dir is None or not prev_dir.is_dir():
        return 0

    for fragment_path in sorted(staging_dir.glob("*.json")):
        try:
            fragment = _load_json(fragment_path)
        except (json.JSONDecodeError, OSError) as error:
            sys.stderr.write(f"unreadable fragment {fragment_path}: {error}\n")
            return 2
        if not isinstance(fragment, dict):
            sys.stderr.write(f"fragment is not an object: {fragment_path}\n")
            return 2
        if _has_production_view(fragment):
            continue
        fragment_id = fragment.get("id")
        category = fragment.get("category")
        if not isinstance(fragment_id, str) or not fragment_id:
            continue
        if not isinstance(category, str) or not category:
            continue
        prev_fragment = prev_dir / "data" / category / f"{fragment_id}.json"
        if not prev_fragment.is_file():
            continue
        sys.stdout.write(f"{fragment_path}\t{prev_fragment}\n")
    return 0


def _apply(fragment_path, summary_file, datauri_file):
    fragment_path = pathlib.Path(fragment_path)
    try:
        fragment = _load_json(fragment_path)
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unreadable fragment {fragment_path}: {error}\n")
        return 2
    if not isinstance(fragment, dict):
        sys.stderr.write(f"fragment is not an object: {fragment_path}\n")
        return 2

    try:
        summary = pathlib.Path(summary_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        sys.stderr.write(f"unreadable summary {summary_file}: {error}\n")
        return 2
    if not summary:
        sys.stderr.write(f"empty summary file: {summary_file}\n")
        return 2

    try:
        src = pathlib.Path(datauri_file).read_text(encoding="utf-8").strip()
    except OSError as error:
        sys.stderr.write(f"unreadable image data uri {datauri_file}: {error}\n")
        return 2
    if not src:
        sys.stderr.write(f"empty image data uri file: {datauri_file}\n")
        return 2

    body = fragment.get("body")
    if not isinstance(body, list):
        sys.stderr.write(f"fragment body is not an array: {fragment_path}\n")
        return 2

    body.append(
        {
            "type": "markdown",
            "view": "production",
            "status": "info",
            "title": "vs production",
            "md": summary,
        }
    )
    body.append(
        {
            "type": "image",
            "view": "production",
            "src": src,
            "alt": "vs production summary",
        }
    )
    fragment["body"] = body
    if "help" not in fragment:
        help_md = _report_help()
        if help_md:
            fragment["help"] = help_md

    fragment_path.write_text(
        json.dumps(fragment, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(f"augmented {fragment_path}\n")
    return 0


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(
            "usage: backfill.py plan <staging-dir> <reports-root>\n"
            "       backfill.py apply <fragment-path> <summary-file> "
            "<image-data-uri-file>\n"
        )
        return 1
    command = argv[0]
    if command == "plan":
        if len(argv) != 3:
            sys.stderr.write("usage: backfill.py plan <staging-dir> <reports-root>\n")
            return 1
        return _plan(argv[1], argv[2])
    if command == "apply":
        if len(argv) != 4:
            sys.stderr.write(
                "usage: backfill.py apply <fragment-path> <summary-file> "
                "<image-data-uri-file>\n"
            )
            return 1
        return _apply(argv[1], argv[2], argv[3])
    sys.stderr.write(f"unknown subcommand '{command}': expected plan | apply\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
