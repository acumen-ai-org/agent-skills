#!/usr/bin/env bash
set -euo pipefail

base_spec=${1:?usage: run-oasdiff.sh <base_spec> <revision_spec> <out_raw>}
revision_spec=${2:?usage: run-oasdiff.sh <base_spec> <revision_spec> <out_raw>}
out_raw=${3:?usage: run-oasdiff.sh <base_spec> <revision_spec> <out_raw>}

oasdiff_image=tufin/oasdiff:1.10.27

if ! command -v docker >/dev/null 2>&1; then
  echo "oasdiff requires Docker, which is not installed." >&2
  echo "Install Docker Engine: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs the pinned image:" >&2
  echo "  docker run --rm -v <dir>:/specs ${oasdiff_image} breaking /specs/<base> /specs/<revision> -f json" >&2
  echo "TOOL oasdiff exit=3"
  exit 3
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not reachable." >&2
  echo "Start Docker, then re-run. The pinned image is ${oasdiff_image}." >&2
  echo "TOOL oasdiff exit=3"
  exit 3
fi

base_dir=$(cd "$(dirname "$base_spec")" && pwd)
base_name=$(basename "$base_spec")
revision_dir=$(cd "$(dirname "$revision_spec")" && pwd)
revision_name=$(basename "$revision_spec")
out_dir=$(cd "$(dirname "$out_raw")" && pwd)
out_name=$(basename "$out_raw")

set +e
docker run --rm \
  -v "$base_dir:/base:ro" \
  -v "$revision_dir:/revision:ro" \
  -v "$out_dir:/out" \
  "$oasdiff_image" \
  breaking "/base/$base_name" "/revision/$revision_name" \
  --format json > "$out_dir/$out_name"
oasdiff_status=$?
set -e

if [ "$oasdiff_status" -ne 0 ] && [ ! -s "$out_dir/$out_name" ]; then
  echo "oasdiff produced no output (exit $oasdiff_status)" >&2
  echo "TOOL oasdiff exit=2"
  exit 2
fi

echo "TOOL oasdiff exit=0"
