#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-trufflehog.sh <target> <out_dir>}
out_dir=${2:?usage: run-trufflehog.sh <target> <out_dir>}

trufflehog_install_url=https://github.com/trufflesecurity/trufflehog#installation
trufflehog_image=trufflesecurity/trufflehog:3.88.0

if [ "${TRUFFLEHOG_AGPL_ACK:-}" != "true" ]; then
  echo "trufflehog is AGPL-3.0; this optional deeper verified-secret pass is off by default." >&2
  echo "Acknowledge the license to enable it: set TRUFFLEHOG_AGPL_ACK=true" >&2
  echo "TOOL run-trufflehog exit=3" >&2
  exit 3
fi

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-trufflehog exit=5" >&2
  exit 5
fi

mkdir -p "$out_dir"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
out_abs=$(cd "$out_dir" && pwd)
raw_path="$out_abs/trufflehog.raw.json"

run_trufflehog() {
  if command -v trufflehog >/dev/null 2>&1; then
    trufflehog filesystem "$target_abs" --only-verified --json >"$raw_path"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$target_abs:/scan:ro" \
      "$trufflehog_image" filesystem /scan --only-verified --json >"$raw_path"
    return $?
  fi
  echo "trufflehog not found and Docker not available." >&2
  echo "Install trufflehog: $trufflehog_install_url" >&2
  echo "Or run via Docker:  docker run --rm -v \"$target_abs:/scan:ro\" $trufflehog_image filesystem /scan --only-verified --json" >&2
  echo "TOOL run-trufflehog exit=3" >&2
  exit 3
}

set +e
run_trufflehog
tool_code=$?
set -e

if [ ! -f "$raw_path" ]; then
  echo "trufflehog produced no output (exit $tool_code)" >&2
  echo "TOOL run-trufflehog exit=2" >&2
  exit 2
fi

echo "wrote $raw_path"
echo "TOOL run-trufflehog exit=0"
