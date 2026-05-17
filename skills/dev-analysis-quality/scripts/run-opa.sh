#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-opa.sh <target> <out_dir> <policy_dir>}
out_dir=${2:?usage: run-opa.sh <target> <out_dir> <policy_dir>}
policy_dir=${3:?usage: run-opa.sh <target> <out_dir> <policy_dir>}

opa_image=openpolicyagent/opa:0.70.0

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-opa exit=5"
  exit 5
fi
if [ ! -d "$policy_dir" ]; then
  echo "policy directory does not exist: $policy_dir" >&2
  echo "TOOL run-opa exit=5"
  exit 5
fi

mkdir -p "$out_dir"
raw_path="$out_dir/opa.raw.json"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
policy_abs=$(cd "$policy_dir" && pwd)
out_abs=$(cd "$out_dir" && pwd)

run_opa() {
  if command -v opa >/dev/null 2>&1; then
    opa eval --format json --data "$policy_abs" --input "$target_abs" 'data' >"$raw_path"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$policy_abs:/policy:ro" \
      -v "$target_abs:/input:ro" \
      -v "$out_abs:/out" \
      "$opa_image" \
      eval --format json --data /policy --input /input 'data' >"$raw_path"
    return $?
  fi
  echo "opa not found and Docker not available." >&2
  echo "Install OPA:        see https://www.openpolicyagent.org/docs/latest/#running-opa" >&2
  echo "Or run via Docker:  docker run --rm -v \"$policy_abs:/policy:ro\" -v \"$target_abs:/input:ro\" -v \"$out_abs:/out\" $opa_image eval --format json --data /policy --input /input 'data'" >&2
  echo "TOOL run-opa exit=3"
  exit 3
}

set +e
run_opa
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "opa produced no output (exit $tool_code)" >&2
  echo "TOOL run-opa exit=2"
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "opa output is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-opa exit=2"
  exit 2
fi

echo "TOOL run-opa exit=0"
