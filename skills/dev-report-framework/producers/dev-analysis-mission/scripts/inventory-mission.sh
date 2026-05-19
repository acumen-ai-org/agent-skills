#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: inventory-mission.sh <repo> <out_dir> [ref-range]}
out_dir=${2:?usage: inventory-mission.sh <repo> <out_dir> [ref-range]}
ref_range=${3:-}

tool_name=inventory-mission

if ! command -v git >/dev/null 2>&1; then
  printf 'git not found. Install it: https://git-scm.com/downloads\n' >&2
  printf 'TOOL %s exit=5\n' "$tool_name"
  exit 5
fi

if [ ! -d "$repo" ] || ! git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'not a git repository: %s\n' "$repo" >&2
  printf 'TOOL %s exit=5\n' "$tool_name"
  exit 5
fi

if [ -n "$ref_range" ] && ! git -C "$repo" rev-parse --quiet --verify "$ref_range^{}" >/dev/null 2>&1; then
  if ! git -C "$repo" log -1 "$ref_range" >/dev/null 2>&1; then
    printf 'invalid ref-range: %s\n' "$ref_range" >&2
    printf 'TOOL %s exit=5\n' "$tool_name"
    exit 5
  fi
fi

mkdir -p "$out_dir"

repo="$repo" out_dir="$out_dir" ref_range="$ref_range" python3 - <<'PY'
import json
import os
import pathlib
import subprocess

repo = pathlib.Path(os.environ["repo"]).resolve()
out_dir = pathlib.Path(os.environ["out_dir"]).resolve()
ref_range = os.environ.get("ref_range", "")

candidate_globs = [
    "MISSION.md",
    "PRODUCT.md",
    "VISION.md",
    "docs/vision*",
    "docs/mission*",
    "docs/product*",
    "docs/strategy*",
    "docs/roadmap*",
    "docs/okr*",
    "OKR*.md",
    "docs/prd*",
    "PRD*.md",
]

external_pointer = os.environ.get("MISSION_DOC")
thin_word_threshold = 40

documents = []
seen = set()


def add_document(path):
    resolved = path.resolve()
    if resolved in seen or not resolved.is_file():
        return
    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    seen.add(resolved)
    word_count = len(text.split())
    try:
        relative = str(resolved.relative_to(repo))
    except ValueError:
        relative = str(resolved)
    documents.append(
        {
            "path": relative,
            "word_count": word_count,
            "thin": word_count < thin_word_threshold,
            "content": text,
        }
    )


if external_pointer:
    add_document(pathlib.Path(external_pointer))

for pattern in candidate_globs:
    for match in sorted(repo.glob(pattern)):
        add_document(match)

substantive = [doc for doc in documents if not doc["thin"]]
mission_docs_found = len(substantive)

change_inventory = {"changed_areas": [], "log_themes": [], "ref_range": ref_range}

if ref_range:
    def git_lines(args):
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    name_status = git_lines(["diff", "--name-only", ref_range])
    area_counts = {}
    for path in name_status:
        top = path.split("/", 1)[0] if "/" in path else path
        area_counts[top] = area_counts.get(top, 0) + 1
    change_inventory["changed_areas"] = [
        {"area": area, "files_changed": count}
        for area, count in sorted(area_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    subjects = git_lines(["log", "--no-merges", "--format=%s", ref_range])
    change_inventory["log_themes"] = [
        {"subject": subject} for subject in subjects
    ]

metrics = {
    "mission_docs_found": mission_docs_found,
    "documents_total": len(documents),
    "thin_documents": len(documents) - mission_docs_found,
    "changed_areas": len(change_inventory["changed_areas"]),
    "log_entries": len(change_inventory["log_themes"]),
}

inventory = {
    "repo": str(repo),
    "documents": documents,
    "substantive_count": mission_docs_found,
    "change_inventory": change_inventory,
    "metrics": metrics,
}

(out_dir / "mission.raw.json").write_text(
    json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

printf 'TOOL %s exit=0\n' "$tool_name"
