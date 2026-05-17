#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-madge.sh <target> <out_dir> [entry]}
out_dir=${2:?usage: run-madge.sh <target> <out_dir> [entry]}
entry=${3:-src}

fragment_id=architecture-madge
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
madge_npm_package="madge@8"

if [ ! -e "${target}/${entry}" ]; then
  echo "entry not found: ${target}/${entry}" >&2
  echo "TOOL madge exit=5"
  exit 5
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "madge requires Node. It is not installed and is never auto-installed." >&2
  echo "Install Node 18+ from https://nodejs.org then detect circular dependencies:" >&2
  echo "  npx --yes ${madge_npm_package} --circular --json '${target}/${entry}'" >&2
  echo "TOOL madge exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
npx --yes "$madge_npm_package" --circular --json "${target}/${entry}" \
  >"$raw_path" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "madge produced no output (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL madge exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL madge exit=${fragment_status}"
exit "$fragment_status"
