#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: collect-diff.sh <repo> <out_dir> <ref_range>}
out_dir=${2:?usage: collect-diff.sh <repo> <out_dir> <ref_range>}
ref_range=${3:?usage: collect-diff.sh <repo> <out_dir> <ref_range>}

plugin_root=${CLAUDE_PLUGIN_ROOT:-}
if [ -z "$plugin_root" ]; then
  echo "CLAUDE_PLUGIN_ROOT must be set to the plugin root" >&2
  echo "TOOL collect-diff exit=2"
  exit 2
fi
shared_collect_history="$plugin_root/scripts/collect-history.sh"
shared_collect_author_activity="$plugin_root/scripts/collect-author-activity.sh"
schema_diff_chain="$plugin_root/skills/dev-analysis-schema/scripts/diff-schemas.sh"

for reused in "$shared_collect_history" "$shared_collect_author_activity" "$schema_diff_chain"; do
  if [ ! -f "$reused" ]; then
    echo "required reusable not found: $reused" >&2
    echo "TOOL collect-diff exit=2"
    exit 2
  fi
done

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL collect-diff exit=5"
  exit 5
fi

normalized_range=${ref_range//.../..}
ref_a=${normalized_range%%..*}
ref_b=${normalized_range##*..}
[ -n "$ref_a" ] || ref_a=$(git -C "$repo" rev-list --max-parents=0 HEAD | tail -n 1)
[ -n "$ref_b" ] || ref_b=HEAD

for endpoint in "$ref_a" "$ref_b"; do
  if ! git -C "$repo" rev-parse --verify --quiet "$endpoint^{commit}" >/dev/null; then
    echo "ref not found in $repo: $endpoint" >&2
    echo "TOOL collect-diff exit=5"
    exit 5
  fi
done

mkdir -p "$out_dir"
history_dir="$out_dir/history"
author_dir="$out_dir/author-activity"
schema_dir="$out_dir/schema"
mkdir -p "$history_dir" "$author_dir" "$schema_dir"

range_pair="$ref_a..$ref_b"

set +e
bash "$shared_collect_history" "$repo" "$history_dir" "$ref_a $ref_b"
collect_history_exit=$?
bash "$shared_collect_author_activity" "$repo" "$author_dir" "$range_pair"
collect_author_exit=$?
bash "$schema_diff_chain" "$repo" "$schema_dir" "$ref_a" "$ref_b"
schema_diff_exit=$?
set -e

for collector_exit in "$collect_history_exit" "$collect_author_exit"; do
  if [ "$collector_exit" -eq 5 ]; then
    echo "TOOL collect-diff exit=5"
    exit 5
  fi
done

REPO="$repo" RANGE="$range_pair" REF_A="$ref_a" REF_B="$ref_b" \
HISTORY="$history_dir/history.json" \
AUTHOR="$author_dir/author-activity.json" \
SCHEMA="$schema_dir/schema-diff.json" \
HISTORY_EXIT="$collect_history_exit" AUTHOR_EXIT="$collect_author_exit" \
SCHEMA_EXIT="$schema_diff_exit" \
python3 - "$out_dir/diff-facts.json" <<'PYTHON'
import json
import os
import sys

out_path = sys.argv[1]


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


history = read_json(os.environ["HISTORY"])
author_activity = read_json(os.environ["AUTHOR"])
schema_diff = read_json(os.environ["SCHEMA"])

totals = {"files_changed": 0, "lines_added": 0, "lines_removed": 0}
by_extension = {}
by_author = {}
if isinstance(history, dict):
    for pair in history.get("pairs", []):
        totals["files_changed"] += pair.get("files_changed", 0)
        totals["lines_added"] += pair.get("lines_added", 0)
        totals["lines_removed"] += pair.get("lines_removed", 0)
        for extension, count in pair.get("by_extension", {}).items():
            by_extension[extension] = by_extension.get(extension, 0) + count
        for name, count in pair.get("by_author", {}).items():
            by_author[name] = by_author.get(name, 0) + count

pr_units = author_activity.get("pr_units", []) if isinstance(author_activity, dict) else []
schema_summary = (
    schema_diff.get("summary", {}) if isinstance(schema_diff, dict) else {}
)

facts = {
    "repo": os.environ["REPO"],
    "range": os.environ["RANGE"],
    "ref_a": os.environ["REF_A"],
    "ref_b": os.environ["REF_B"],
    "sources": {
        "history": {
            "path": "history/history.json",
            "exit": int(os.environ["HISTORY_EXIT"]),
            "present": history is not None,
        },
        "author_activity": {
            "path": "author-activity/author-activity.json",
            "exit": int(os.environ["AUTHOR_EXIT"]),
            "present": author_activity is not None,
        },
        "schema": {
            "path": "schema/schema-diff.json",
            "exit": int(os.environ["SCHEMA_EXIT"]),
            "present": schema_diff is not None,
        },
    },
    "diff": {
        "totals": totals,
        "by_extension": dict(
            sorted(by_extension.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "by_author": dict(sorted(by_author.items(), key=lambda kv: (-kv[1], kv[0]))),
        "pr_unit_count": len(pr_units),
    },
    "schema": {
        "has_diff": bool(schema_summary.get("hasDiff", False)),
        "public_breaking": schema_summary.get("publicBreaking", 0),
        "private_breaking": schema_summary.get("privateBreaking", 0),
        "total_changes": schema_summary.get("totalChanges", 0),
        "tool_missing": bool(schema_diff.get("toolMissing", False))
        if isinstance(schema_diff, dict)
        else False,
    },
}

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(facts, handle, indent=2, sort_keys=True)

print(
    "FACTS files_changed={} pr_units={} schema_has_diff={} public_breaking={}".format(
        totals["files_changed"],
        len(pr_units),
        facts["schema"]["has_diff"],
        facts["schema"]["public_breaking"],
    )
)
PYTHON

echo "TOOL collect-diff exit=0"
