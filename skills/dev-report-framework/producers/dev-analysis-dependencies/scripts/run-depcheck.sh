#!/usr/bin/env bash
set -euo pipefail

depcheck_image=owasp/dependency-check:11.1.0

usage() {
  echo "usage: run-depcheck.sh <target> <out_dir> [id]" >&2
  echo "  <target>   project directory with declared dependencies (.NET/F#/TS-JS/Py)" >&2
  echo "  <out_dir>  directory for <id>.raw.json" >&2
  echo "  [id]       fragment id stem (default: dependency-supply-chain)" >&2
  exit 1
}

target=${1:-}
out_dir=${2:-}
fragment_id=${3:-dependency-supply-chain}
[ -n "$target" ] || usage
[ -n "$out_dir" ] || usage

if [ ! -d "$target" ]; then
  echo "target directory not found: $target" >&2
  echo "TOOL dependency-check exit=5" >&2
  exit 5
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run OWASP Dependency-Check and was not found." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs:" >&2
  echo "  docker run --rm -v \"\$(realpath '$target')\":/src:ro -v \"\$(realpath '$out_dir')\":/report ${depcheck_image} --scan /src --format JSON --out /report --project ${fragment_id} --noupdate" >&2
  echo "TOOL dependency-check exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
target_abs=$(realpath "$target")
out_abs=$(realpath "$out_dir")
report_path="${out_abs}/dependency-check-report.json"
raw_path="${out_abs}/${fragment_id}.raw.json"

set +e
docker run --rm \
  -v "${target_abs}":/src:ro \
  -v "${out_abs}":/report \
  "${depcheck_image}" \
  --scan /src --format JSON --out /report \
  --project "${fragment_id}" --noupdate
tool_status=$?
set -e

if [ "$tool_status" -ne 0 ] || [ ! -s "$report_path" ]; then
  echo "Dependency-Check produced no usable JSON (exit ${tool_status}); output kept under ${out_abs}" >&2
  echo "TOOL dependency-check exit=2" >&2
  exit 2
fi

mv "$report_path" "$raw_path"
echo "wrote ${raw_path}"
echo "TOOL dependency-check exit=0"
