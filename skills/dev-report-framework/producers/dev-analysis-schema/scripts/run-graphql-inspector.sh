#!/usr/bin/env bash
set -euo pipefail

base_sdl=${1:?usage: run-graphql-inspector.sh <base_sdl> <revision_sdl> <out_raw>}
revision_sdl=${2:?usage: run-graphql-inspector.sh <base_sdl> <revision_sdl> <out_raw>}
out_raw=${3:?usage: run-graphql-inspector.sh <base_sdl> <revision_sdl> <out_raw>}

graphql_inspector_package=@graphql-inspector/cli@5.0.0

if ! command -v npx >/dev/null 2>&1; then
  echo "graphql-inspector requires Node.js (npx), which is not installed." >&2
  echo "Install Node.js LTS: https://nodejs.org/en/download" >&2
  echo "Then this script runs the pinned package:" >&2
  echo "  npx --yes ${graphql_inspector_package} diff <base.graphql> <revision.graphql>" >&2
  echo "TOOL graphql-inspector exit=3"
  exit 3
fi

set +e
npx --yes "$graphql_inspector_package" diff \
  "$base_sdl" "$revision_sdl" \
  --output json > "$out_raw" 2>"$out_raw.stderr"
inspector_status=$?
set -e

if [ ! -s "$out_raw" ]; then
  if grep -qi 'no changes' "$out_raw.stderr" 2>/dev/null; then
    printf '%s\n' '{"changes":[]}' > "$out_raw"
    rm -f "$out_raw.stderr"
    echo "TOOL graphql-inspector exit=0"
    exit 0
  fi
  echo "graphql-inspector produced no output (exit $inspector_status)" >&2
  cat "$out_raw.stderr" >&2 2>/dev/null || true
  echo "TOOL graphql-inspector exit=2"
  exit 2
fi

rm -f "$out_raw.stderr"
echo "TOOL graphql-inspector exit=0"
