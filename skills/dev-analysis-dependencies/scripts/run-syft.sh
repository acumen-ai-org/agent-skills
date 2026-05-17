#!/usr/bin/env bash
set -euo pipefail

syft_image=anchore/syft:v1.18.1

usage() {
  echo "usage: run-syft.sh <target> <out_dir> [id]" >&2
  echo "  <target>   filesystem path to inventory into an SBOM" >&2
  echo "  <out_dir>  directory for <id>.sbom.raw.json (CycloneDX JSON)" >&2
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
  echo "TOOL syft exit=5" >&2
  exit 5
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run Syft and was not found." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs:" >&2
  echo "  docker run --rm -v \"\$(realpath '$target')\":/scan:ro -v \"\$(realpath '$out_dir')\":/out ${syft_image} scan dir:/scan -o cyclonedx-json=/out/${fragment_id}.sbom.raw.json" >&2
  echo "TOOL syft exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
target_abs=$(realpath "$target")
out_abs=$(realpath "$out_dir")
sbom_path="${out_abs}/${fragment_id}.sbom.raw.json"

set +e
docker run --rm \
  -v "${target_abs}":/scan:ro \
  -v "${out_abs}":/out \
  "${syft_image}" scan dir:/scan \
  -o "cyclonedx-json=/out/${fragment_id}.sbom.raw.json"
tool_status=$?
set -e

if [ "$tool_status" -ne 0 ] || [ ! -s "$sbom_path" ]; then
  echo "Syft produced no usable SBOM (exit ${tool_status}); raw kept at ${sbom_path}" >&2
  echo "TOOL syft exit=2" >&2
  exit 2
fi

echo "wrote ${sbom_path}"
echo "TOOL syft exit=0"
