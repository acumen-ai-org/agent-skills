#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-scc.sh <target> <out_dir>}
out_dir=${2:?usage: run-scc.sh <target> <out_dir>}

scc_image=ghcr.io/boyter/scc:v3.5.0

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-scc exit=5"
  exit 5
fi

mkdir -p "$out_dir"
raw_path="$out_dir/scc.raw.json"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")

run_scc() {
  if command -v scc >/dev/null 2>&1; then
    scc --format json --by-file "$target_abs" >"$raw_path"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$target_abs:/src:ro" \
      "$scc_image" \
      --format json --by-file /src >"$raw_path"
    return $?
  fi
  echo "scc not found and Docker not available." >&2
  echo "Install scc:        go install github.com/boyter/scc/v3@latest" >&2
  echo "Or run via Docker:  docker run --rm -v \"$target_abs:/src:ro\" $scc_image --format json --by-file /src" >&2
  echo "TOOL run-scc exit=3"
  exit 3
}

set +e
run_scc
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "scc produced no output (exit $tool_code)" >&2
  echo "TOOL run-scc exit=2"
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "scc output is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-scc exit=2"
  exit 2
fi

echo "TOOL run-scc exit=0"
