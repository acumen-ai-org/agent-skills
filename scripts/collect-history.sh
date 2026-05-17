#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: collect-history.sh <repo> <out_dir> <ref_list>}
out_dir=${2:?usage: collect-history.sh <repo> <out_dir> <ref_list>}
ref_list=${3:?usage: collect-history.sh <repo> <out_dir> <ref_list>}

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL collect-history exit=5"
  exit 5
fi

mkdir -p "$out_dir"

normalized_refs=${ref_list//,/ }
read -r -a refs <<<"$normalized_refs"

if [ "${#refs[@]}" -lt 2 ]; then
  echo "ref_list needs at least two release refs, got: $ref_list" >&2
  echo "TOOL collect-history exit=5"
  exit 5
fi

for ref in "${refs[@]}"; do
  if ! git -C "$repo" rev-parse --verify --quiet "$ref^{commit}" >/dev/null; then
    echo "ref not found in $repo: $ref" >&2
    echo "TOOL collect-history exit=5"
    exit 5
  fi
done

dirstat_path="$out_dir/history-dirstat.tsv"
numstat_path="$out_dir/history-numstat.tsv"
: >"$dirstat_path"
: >"$numstat_path"

pair_index=0
while [ "$pair_index" -lt $(( ${#refs[@]} - 1 )) ]; do
  older=${refs[$pair_index]}
  newer=${refs[$(( pair_index + 1 ))]}
  pair_label="$older..$newer"

  while IFS= read -r line; do
    [ -n "$line" ] && printf '%s\t%s\n' "$pair_label" "$line" >>"$dirstat_path"
  done < <(git -C "$repo" diff --dirstat=files,0 "$older" "$newer")

  while IFS= read -r line; do
    [ -n "$line" ] && printf '%s\t%s\n' "$pair_label" "$line" >>"$numstat_path"
  done < <(git -C "$repo" diff --numstat "$older" "$newer")

  pair_index=$(( pair_index + 1 ))
done

REFS="${refs[*]}" NUMSTAT="$numstat_path" DIRSTAT="$dirstat_path" REPO="$repo" \
python3 - "$out_dir/history.json" <<'PYTHON'
import collections
import json
import os
import subprocess
import sys

out_path = sys.argv[1]
refs = os.environ["REFS"].split()
repo = os.environ["REPO"]
repo_abs = os.path.abspath(repo)


def author_for(repo_path, older, newer):
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "--no-merges", "--pretty=%aN", f"{older}..{newer}"],
        capture_output=True,
        text=True,
        check=False,
    )
    counts = collections.Counter()
    for name in result.stdout.splitlines():
        name = name.strip()
        if name:
            counts[name] += 1
    return counts


def extension_of(path):
    dot = path.rfind(".")
    slash = path.rfind("/")
    if dot > slash and dot != -1:
        return path[dot + 1:]
    return "(none)"


def folder_of(path):
    slash = path.rfind("/")
    if slash == -1:
        return "(root)"
    return path[:slash]


def file_of(path):
    slash = path.rfind("/")
    if slash == -1:
        return path
    return path[slash + 1:]


pairs = []
numstat_rows = collections.defaultdict(list)
extension_tree = {}
with open(os.environ["NUMSTAT"], encoding="utf-8") as handle:
    for raw in handle:
        raw = raw.rstrip("\n")
        if not raw:
            continue
        parts = raw.split("\t")
        if len(parts) < 4:
            continue
        pair_label, added, removed, path = parts[0], parts[1], parts[2], parts[3]
        numstat_rows[pair_label].append((added, removed, path))
        extension = extension_of(path)
        folder = folder_of(path)
        name = file_of(path)
        ext_node = extension_tree.setdefault(
            extension, {"files_changed": 0, "folders": {}}
        )
        ext_node["files_changed"] += 1
        folder_node = ext_node["folders"].setdefault(
            folder, {"files_changed": 0, "files": {}}
        )
        folder_node["files_changed"] += 1
        file_entry = folder_node["files"].setdefault(name, {"count": 0, "path": path})
        file_entry["count"] += 1

for index in range(len(refs) - 1):
    older = refs[index]
    newer = refs[index + 1]
    label = f"{older}..{newer}"
    by_extension = collections.Counter()
    files_changed = 0
    added_total = 0
    removed_total = 0
    for added, removed, path in numstat_rows.get(label, []):
        files_changed += 1
        if added.isdigit():
            added_total += int(added)
        if removed.isdigit():
            removed_total += int(removed)
        by_extension[extension_of(path)] += 1
    authors = author_for(repo, older, newer)
    pairs.append(
        {
            "pair": label,
            "older": older,
            "newer": newer,
            "files_changed": files_changed,
            "lines_added": added_total,
            "lines_removed": removed_total,
            "by_extension": dict(sorted(by_extension.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_author": dict(sorted(authors.items(), key=lambda kv: (-kv[1], kv[0]))),
        }
    )

extension_tree_sorted = []
for extension, ext_node in sorted(
    extension_tree.items(), key=lambda kv: (-kv[1]["files_changed"], kv[0])
):
    folders_sorted = []
    for folder, folder_node in sorted(
        ext_node["folders"].items(),
        key=lambda kv: (-kv[1]["files_changed"], kv[0]),
    ):
        files_sorted = [
            {
                "file": name,
                "files_changed": entry["count"],
                "path": entry["path"],
            }
            for name, entry in sorted(
                folder_node["files"].items(),
                key=lambda kv: (-kv[1]["count"], kv[0]),
            )
        ]
        folder_path = "" if folder == "(root)" else folder
        folders_sorted.append(
            {
                "folder": folder,
                "path": folder_path,
                "files_changed": folder_node["files_changed"],
                "files": files_sorted,
            }
        )
    extension_tree_sorted.append(
        {
            "extension": extension,
            "files_changed": ext_node["files_changed"],
            "folders": folders_sorted,
        }
    )

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(
        {
            "repo": repo_abs,
            "refs": refs,
            "pairs": pairs,
            "extension_tree": extension_tree_sorted,
        },
        handle,
        indent=2,
        sort_keys=True,
    )
PYTHON

echo "TOOL collect-history exit=0"
