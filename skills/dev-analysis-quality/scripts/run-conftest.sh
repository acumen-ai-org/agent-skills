#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-conftest.sh <target> <out_dir> <policy_dir>}
out_dir=${2:?usage: run-conftest.sh <target> <out_dir> <policy_dir>}
policy_dir=${3:?usage: run-conftest.sh <target> <out_dir> <policy_dir>}

conftest_image=openpolicyagent/conftest:v0.56.0

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-conftest exit=5"
  exit 5
fi
if [ ! -d "$policy_dir" ]; then
  echo "policy directory does not exist: $policy_dir" >&2
  echo "TOOL run-conftest exit=5"
  exit 5
fi

mkdir -p "$out_dir"
raw_path="$out_dir/conftest.raw.json"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
policy_abs=$(cd "$policy_dir" && pwd)

run_conftest() {
  if command -v conftest >/dev/null 2>&1; then
    conftest test --output json --policy "$policy_abs" "$target_abs" >"$raw_path"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$policy_abs:/policy:ro" \
      -v "$target_abs:/project/$(basename "$target_abs"):ro" \
      "$conftest_image" \
      test --output json --policy /policy "/project/$(basename "$target_abs")" >"$raw_path"
    return $?
  fi
  echo "conftest not found and Docker not available." >&2
  echo "Install Conftest:   see https://www.conftest.dev/install/" >&2
  echo "Or run via Docker:  docker run --rm -v \"$policy_abs:/policy:ro\" -v \"$target_abs:/project/$(basename "$target_abs"):ro\" $conftest_image test --output json --policy /policy /project/$(basename "$target_abs")" >&2
  echo "TOOL run-conftest exit=3"
  exit 3
}

set +e
run_conftest
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "conftest produced no output (exit $tool_code)" >&2
  echo "TOOL run-conftest exit=2"
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "conftest output is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-conftest exit=2"
  exit 2
fi

echo "TOOL run-conftest exit=0"
