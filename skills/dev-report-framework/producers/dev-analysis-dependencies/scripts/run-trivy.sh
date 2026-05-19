#!/usr/bin/env bash
set -euo pipefail

trivy_image=aquasec/trivy:0.58.0

usage() {
  echo "usage: run-trivy.sh <target> <out_dir> [id]" >&2
  echo "  <target>   filesystem path to scan for vulnerable dependencies" >&2
  echo "  <out_dir>  directory for <id>.raw.json" >&2
  echo "  [id]       fragment id stem (default: dependency-supply-chain)" >&2
  exit 1
}

target=${1:-}
out_dir=${2:-}
fragment_id=${3:-dependency-supply-chain}
[ -n "$target" ] || usage
[ -n "$out_dir" ] || usage

if [ ! -e "$target" ]; then
  echo "target not found: $target" >&2
  echo "TOOL trivy exit=5" >&2
  exit 5
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run Trivy and was not found." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs:" >&2
  echo "  docker run --rm -v \"\$(realpath '$target')\":/scan:ro -v \"\$(realpath '$out_dir')\":/out ${trivy_image} filesystem --quiet --scanners vuln --format json --output /out/${fragment_id}.raw.json /scan" >&2
  echo "TOOL trivy exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
target_abs=$(realpath "$target")
out_abs=$(realpath "$out_dir")
raw_path="${out_abs}/${fragment_id}.raw.json"

set +e
docker run --rm \
  -v "${target_abs}":/scan:ro \
  -v "${out_abs}":/out \
  "${trivy_image}" filesystem \
  --quiet --scanners vuln --format json \
  --output "/out/${fragment_id}.raw.json" /scan
tool_status=$?
set -e

if [ "$tool_status" -ne 0 ] || [ ! -s "$raw_path" ]; then
  echo "Trivy produced no usable JSON (exit ${tool_status}); raw kept at ${raw_path}" >&2
  echo "TOOL trivy exit=2" >&2
  exit 2
fi

echo "wrote ${raw_path}"
echo "TOOL trivy exit=0"
