#!/usr/bin/env bash
set -euo pipefail

grype_image=anchore/grype:v0.87.0

usage() {
  echo "usage: run-grype.sh <target> <out_dir> [id]" >&2
  echo "  <target>   filesystem path OR a Syft SBOM JSON file to match against advisories" >&2
  echo "  <out_dir>  directory for <id>.grype.raw.json" >&2
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
  echo "TOOL grype exit=5" >&2
  exit 5
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run Grype and was not found." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs:" >&2
  echo "  docker run --rm -v \"\$(realpath '$target')\":/scan:ro -v \"\$(realpath '$out_dir')\":/out ${grype_image} dir:/scan -o json --file /out/${fragment_id}.grype.raw.json" >&2
  echo "TOOL grype exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
target_abs=$(realpath "$target")
out_abs=$(realpath "$out_dir")
raw_path="${out_abs}/${fragment_id}.grype.raw.json"

if [ -f "$target_abs" ]; then
  scan_source="sbom:/scan/$(basename "$target_abs")"
  mount_source=$(dirname "$target_abs")
else
  scan_source="dir:/scan"
  mount_source="$target_abs"
fi

set +e
docker run --rm \
  -v "${mount_source}":/scan:ro \
  -v "${out_abs}":/out \
  "${grype_image}" "${scan_source}" \
  -o json --file "/out/${fragment_id}.grype.raw.json"
tool_status=$?
set -e

if [ "$tool_status" -ne 0 ] || [ ! -s "$raw_path" ]; then
  echo "Grype produced no usable JSON (exit ${tool_status}); raw kept at ${raw_path}" >&2
  echo "TOOL grype exit=2" >&2
  exit 2
fi

echo "wrote ${raw_path}"
echo "TOOL grype exit=0"
