#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: collect-author-activity.sh <repo> <out_dir> <ref_range>}
out_dir=${2:?usage: collect-author-activity.sh <repo> <out_dir> <ref_range>}
ref_range=${3:?usage: collect-author-activity.sh <repo> <out_dir> <ref_range>}

pr_unit_strategy=${PR_UNIT_STRATEGY:-azure-squash}
squash_generic_pattern=${SQUASH_GENERIC_PATTERN:-'(#\d+)'}

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL collect-author-activity exit=5"
  exit 5
fi

range_left=${ref_range%%..*}
range_right=${ref_range##*..}
for endpoint in "$range_left" "$range_right"; do
  if [ -n "$endpoint" ] && ! git -C "$repo" rev-parse --verify --quiet "$endpoint^{commit}" >/dev/null; then
    echo "ref not found in $repo: $endpoint" >&2
    echo "TOOL collect-author-activity exit=5"
    exit 5
  fi
done

mkdir -p "$out_dir"
raw_log_path="$out_dir/author-activity-log.txt"
record_separator=$'\x1e'
field_separator=$'\x1f'

case "$pr_unit_strategy" in
  azure-squash | squash-generic)
    git -C "$repo" log --first-parent --no-merges \
      --pretty="format:%x1e%H%x1f%aN%x1f%aE%x1f%s%x1f%b%x1f" "$ref_range" \
      >"$raw_log_path"
    ;;
  merge)
    git -C "$repo" log --merges --first-parent \
      --pretty="format:%x1e%H%x1f%aN%x1f%aE%x1f%s%x1f%b%x1f" "$ref_range" \
      >"$raw_log_path"
    ;;
  trailer)
    git -C "$repo" log --first-parent --no-merges \
      --pretty="format:%x1e%H%x1f%aN%x1f%aE%x1f%s%x1f%b%x1f%(trailers:key=Pull-Request,valueonly)%x1f" "$ref_range" \
      >"$raw_log_path"
    ;;
  *)
    echo "unknown PR_UNIT_STRATEGY: $pr_unit_strategy (azure-squash|merge|trailer|squash-generic)" >&2
    echo "TOOL collect-author-activity exit=1"
    exit 1
    ;;
esac

mailmap_path="$repo/.mailmap"
[ -f "$mailmap_path" ] || mailmap_path=""

vibe_definition_path=""
vibe_search_paths=(
  "docs/vibe-coder.md"
  "docs/vibe-coder-definition.md"
  ".github/vibe-coder.md"
  "CONTRIBUTING.md"
  "docs/engineering.md"
  "docs/engineering-guidelines.md"
)
if [ -n "${VIBE_CODER_DEFINITION:-}" ] && [ -f "$repo/$VIBE_CODER_DEFINITION" ]; then
  vibe_definition_path="$repo/$VIBE_CODER_DEFINITION"
else
  for candidate in "${vibe_search_paths[@]}"; do
    if [ -f "$repo/$candidate" ] && grep -qiE '(^|[^a-z])vibe.coder' "$repo/$candidate"; then
      vibe_definition_path="$repo/$candidate"
      break
    fi
  done
fi

az_available=false
if command -v az >/dev/null 2>&1 && az account show >/dev/null 2>&1; then
  az_available=true
fi

REPO="$repo" RAW_LOG="$raw_log_path" STRATEGY="$pr_unit_strategy" \
SQUASH_PATTERN="$squash_generic_pattern" MAILMAP="$mailmap_path" \
VIBE_PATH="$vibe_definition_path" AZ_AVAILABLE="$az_available" \
RS="$record_separator" FS="$field_separator" \
python3 - "$out_dir/author-activity.json" <<'PYTHON'
import json
import os
import re
import subprocess
import sys

out_path = sys.argv[1]
repo = os.environ["REPO"]
repo_abs = os.path.abspath(repo)
strategy = os.environ["STRATEGY"]
record_sep = os.environ["RS"]
field_sep = os.environ["FS"]
az_available = os.environ["AZ_AVAILABLE"] == "true"

azure_subject = re.compile(r"^Merged PR (\d+): (.+)$")
related_items = re.compile(r"Related work items:\s*((?:#\d+)(?:,\s*#\d+)*)")
trailer_pr = re.compile(r"#?(\d+)")
squash_pattern = re.compile(os.environ["SQUASH_PATTERN"])

mailmap = {}
mailmap_path = os.environ["MAILMAP"]
if mailmap_path:
    with open(mailmap_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            emails = re.findall(r"<([^>]+)>", line)
            names = re.findall(r"^([^<]+?)\s*<", line)
            canonical_name = names[0].strip() if names else None
            if canonical_name and emails:
                for email in emails:
                    mailmap[email.strip().lower()] = canonical_name


def canonical_author(name, email):
    key = (email or "").strip().lower()
    if key in mailmap:
        return mailmap[key]
    return name.strip() if name else email


def numstat_for(sha):
    result = subprocess.run(
        ["git", "-C", repo, "show", "--first-parent", "--numstat", "--format=", sha],
        capture_output=True,
        text=True,
        check=False,
    )
    rows = []
    for raw in result.stdout.splitlines():
        raw = raw.rstrip("\n")
        if not raw:
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        rows.append({"added": parts[0], "removed": parts[1], "path": parts[2]})
    return rows


def static_pattern_hint(rows):
    existing_dirs = set()
    existing_top = set()
    result = subprocess.run(
        ["git", "-C", repo, "ls-tree", "-r", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    for path in result.stdout.splitlines():
        path = path.strip()
        if not path:
            continue
        if "/" in path:
            existing_dirs.add(path.rsplit("/", 1)[0])
            existing_top.add(path.split("/", 1)[0])
        else:
            existing_top.add(path)
    new_files_in_new_dirs = 0
    new_top_modules = 0
    edits_to_existing = 0
    for row in rows:
        path = row["path"]
        added = row["added"]
        removed = row["removed"]
        is_addition = removed == "0" and added != "0"
        directory = path.rsplit("/", 1)[0] if "/" in path else ""
        top = path.split("/", 1)[0] if "/" in path else path
        if is_addition and directory and directory not in existing_dirs:
            new_files_in_new_dirs += 1
        if is_addition and top not in existing_top:
            new_top_modules += 1
        if not is_addition:
            edits_to_existing += 1
    return {
        "new_files_in_new_directories": new_files_in_new_dirs,
        "new_top_level_modules": new_top_modules,
        "edits_to_existing_files": edits_to_existing,
    }


def work_item_type(work_item_id):
    if not az_available:
        return None
    result = subprocess.run(
        [
            "az",
            "boards",
            "work-item",
            "show",
            "--id",
            str(work_item_id),
            "--query",
            'fields."System.WorkItemType"',
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value or None


def parse_record(record):
    fields = record.split(field_sep)
    if len(fields) < 5:
        return None
    sha = fields[0].strip()
    name = fields[1]
    email = fields[2]
    subject = fields[3]
    body = fields[4]
    trailer = fields[5].strip() if len(fields) > 5 else ""
    if not sha:
        return None

    pr_number = None
    title = subject
    if strategy == "azure-squash":
        match = azure_subject.match(subject)
        if not match:
            return None
        pr_number = int(match.group(1))
        title = match.group(2).strip()
    elif strategy == "merge":
        merge_pr = re.search(r"#(\d+)", subject)
        pr_number = int(merge_pr.group(1)) if merge_pr else None
    elif strategy == "trailer":
        if not trailer:
            return None
        trailer_match = trailer_pr.search(trailer)
        pr_number = int(trailer_match.group(1)) if trailer_match else None
    elif strategy == "squash-generic":
        squash_match = squash_pattern.search(subject)
        if not squash_match:
            return None
        digits = re.search(r"\d+", squash_match.group(0))
        pr_number = int(digits.group(0)) if digits else None

    body_lines = []
    for line in body.splitlines():
        if related_items.search(line):
            continue
        body_lines.append(line)
    body_text = "\n".join(body_lines).strip()

    work_items = []
    for related in related_items.finditer(body):
        for token in re.findall(r"#(\d+)", related.group(1)):
            work_items.append(int(token))

    rows = numstat_for(sha)
    work_item_records = []
    for work_item_id in work_items:
        work_item_records.append(
            {"id": work_item_id, "type": work_item_type(work_item_id)}
        )

    return {
        "sha": sha,
        "pr": pr_number,
        "title": title,
        "author": canonical_author(name, email),
        "raw_author_name": name.strip(),
        "raw_author_email": email.strip(),
        "body": body_text,
        "work_items": work_item_records,
        "changed_paths": [row["path"] for row in rows],
        "numstat": rows,
        "static_pattern_hint": static_pattern_hint(rows),
    }


with open(os.environ["RAW_LOG"], encoding="utf-8", errors="replace") as handle:
    raw = handle.read()

pr_units = []
for record in raw.split(record_sep):
    record = record.strip("\n")
    if not record.strip():
        continue
    parsed = parse_record(record)
    if parsed is not None:
        pr_units.append(parsed)

vibe_definition = None
vibe_path = os.environ["VIBE_PATH"]
if vibe_path:
    with open(vibe_path, encoding="utf-8", errors="replace") as handle:
        vibe_definition = {
            "path": os.path.relpath(vibe_path, repo),
            "text": handle.read(),
        }

bundle = {
    "repo": repo_abs,
    "strategy": strategy,
    "pr_unit_count": len(pr_units),
    "az_work_item_types_resolved": az_available,
    "vibe_coder_definition": vibe_definition,
    "pr_units": pr_units,
}

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(bundle, handle, indent=2, sort_keys=True)
PYTHON

echo "TOOL collect-author-activity exit=0"
