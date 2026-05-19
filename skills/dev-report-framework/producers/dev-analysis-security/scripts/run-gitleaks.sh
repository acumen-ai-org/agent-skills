#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-gitleaks.sh <target> <out_dir>}
out_dir=${2:?usage: run-gitleaks.sh <target> <out_dir>}

gitleaks_image=zricethezav/gitleaks:v8.21.2

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-gitleaks exit=5" >&2
  exit 5
fi

mkdir -p "$out_dir"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
out_abs=$(cd "$out_dir" && pwd)
raw_path="$out_abs/gitleaks.raw.json"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run gitleaks and was not found." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs:" >&2
  echo "  docker run --rm -v \"$target_abs:/scan:ro\" -v \"$out_abs:/out\" $gitleaks_image detect --source /scan --no-git --report-format json --report-path /out/gitleaks.raw.json --exit-code 0" >&2
  echo "TOOL run-gitleaks exit=3" >&2
  exit 3
fi

if git -C "$target_abs" rev-parse --git-dir >/dev/null 2>&1; then
  scan_mode=()
else
  scan_mode=(--no-git)
fi

set +e
docker run --rm \
  -v "$target_abs:/scan:ro" \
  -v "$out_abs:/out" \
  "$gitleaks_image" detect \
  --source /scan "${scan_mode[@]}" \
  --report-format json \
  --report-path /out/gitleaks.raw.json \
  --exit-code 0
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "gitleaks produced no report (exit $tool_code); raw kept at $raw_path" >&2
  echo "TOOL run-gitleaks exit=2" >&2
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "gitleaks report is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-gitleaks exit=2" >&2
  exit 2
fi

echo "wrote $raw_path"
echo "TOOL run-gitleaks exit=0"
