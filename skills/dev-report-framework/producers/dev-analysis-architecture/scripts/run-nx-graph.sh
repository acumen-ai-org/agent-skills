#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-nx-graph.sh <nx-workspace-dir> <out_dir>}
out_dir=${2:?usage: run-nx-graph.sh <nx-workspace-dir> <out_dir>}

fragment_id=architecture-nx
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
nx_npm_package="nx@latest"

if [ ! -d "$target" ]; then
  echo "target is not a directory: $target" >&2
  echo "TOOL nx exit=5"
  exit 5
fi
if [ ! -f "${target}/nx.json" ]; then
  echo "no nx.json in ${target}; not an Nx workspace" >&2
  echo "TOOL nx exit=5"
  exit 5
fi

if ! command -v npx >/dev/null 2>&1; then
  echo "Nx Graph requires Node. It is not installed and is never auto-installed." >&2
  echo "Install Node 18+ from https://nodejs.org then export the project graph:" >&2
  echo "  (cd '${target}' && npx --yes ${nx_npm_package} graph --file='${raw_path}')" >&2
  echo "TOOL nx exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
( cd "$target" && npx --yes "$nx_npm_package" graph --file="$raw_path" ) \
  >"${out_dir}/${fragment_id}.stdout.log" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "nx graph produced no graph file (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL nx exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL nx exit=${fragment_status}"
exit "$fragment_status"
