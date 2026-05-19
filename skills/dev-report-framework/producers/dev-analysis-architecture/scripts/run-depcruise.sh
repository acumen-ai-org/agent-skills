#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-depcruise.sh <target> <out_dir> [glob]}
out_dir=${2:?usage: run-depcruise.sh <target> <out_dir> [glob]}
source_glob=${3:-src}

fragment_id=architecture-depcruise
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
depcruise_npm_package="dependency-cruiser@16"

if [ ! -d "$target" ]; then
  echo "target is not a directory: $target" >&2
  echo "TOOL depcruise exit=5"
  exit 5
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "dependency-cruiser requires Node. It is not installed and is never auto-installed." >&2
  echo "Install Node 18+ from https://nodejs.org then run dependency-cruiser via npx:" >&2
  echo "  npx --yes ${depcruise_npm_package} --no-config --output-type json --include-only '^${source_glob}' '${target}/${source_glob}'" >&2
  echo "TOOL depcruise exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
npx --yes "$depcruise_npm_package" \
  --no-config \
  --output-type json \
  --include-only "^${source_glob}" \
  "${target}/${source_glob}" >"$raw_path" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "dependency-cruiser produced no output (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL depcruise exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL depcruise exit=${fragment_status}"
exit "$fragment_status"
