#!/usr/bin/env bash
set -euo pipefail
repo=${DRP_REPO:-.}
id=${1:?usage: run_tool.sh <id> <command> <out_dir> [report_file] [timeoutSeconds]}
command_str=${2:?usage: run_tool.sh <id> <command> <out_dir> [report_file] [timeoutSeconds]}
out_dir=${3:?usage: run_tool.sh <id> <command> <out_dir> [report_file] [timeoutSeconds]}
report=${4:-$id.txt}
timeout_s=${5:-1800}

mkdir -p "$repo/$out_dir"
report_path="$repo/$out_dir/$report"
exit_path="$repo/$out_dir/$id.exit"

if command -v timeout >/dev/null 2>&1; then
  runner=(timeout "$timeout_s" bash -c "$command_str")
else
  runner=(bash -c "$command_str")
fi

set +e
( cd "$repo" && "${runner[@]}" ) > "$report_path" 2>&1
code=$?
set -e
printf '%s\n' "$code" > "$exit_path"
echo "tool '$id' exit=$code -> $out_dir/$report"
exit 0
