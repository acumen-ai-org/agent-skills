#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-semgrep.sh <target> <out_dir> <ruleset>}
out_dir=${2:?usage: run-semgrep.sh <target> <out_dir> <ruleset>}
ruleset=${3:?usage: run-semgrep.sh <target> <out_dir> <ruleset>}

semgrep_image=semgrep/semgrep:1.107.0

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-semgrep exit=5"
  exit 5
fi

mkdir -p "$out_dir"
raw_path="$out_dir/semgrep.raw.json"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
out_abs=$(cd "$out_dir" && pwd)

run_semgrep() {
  if command -v semgrep >/dev/null 2>&1; then
    semgrep --config "$ruleset" --json --quiet --output "$raw_path" "$target_abs"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$target_abs:/src:ro" \
      -v "$out_abs:/out" \
      "$semgrep_image" \
      semgrep --config "$ruleset" --json --quiet --output "/out/semgrep.raw.json" /src
    return $?
  fi
  echo "semgrep not found and Docker not available." >&2
  echo "Install Semgrep CE:    python3 -m pip install --user semgrep" >&2
  echo "Or run via Docker:     docker run --rm -v \"$target_abs:/src:ro\" -v \"$out_abs:/out\" $semgrep_image semgrep --config $ruleset --json --quiet --output /out/semgrep.raw.json /src" >&2
  echo "TOOL run-semgrep exit=3"
  exit 3
}

set +e
run_semgrep
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "semgrep produced no output (exit $tool_code)" >&2
  echo "TOOL run-semgrep exit=2"
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "semgrep output is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-semgrep exit=2"
  exit 2
fi

echo "TOOL run-semgrep exit=0"
