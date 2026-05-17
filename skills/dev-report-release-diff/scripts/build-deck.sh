#!/usr/bin/env bash
set -euo pipefail

slides_md=${1:?usage: build-deck.sh <slides-md> <out_dir>}
out_dir=${2:?usage: build-deck.sh <slides-md> <out_dir>}

slidev_package=@slidev/cli@0.49.29
node_install_url=https://nodejs.org/en/download
slidev_npx_invocation="npx --yes $slidev_package build \"$slides_md\" --out \"$out_dir\""

if [ ! -f "$slides_md" ]; then
  echo "slides markdown not found: $slides_md" >&2
  echo "TOOL build-deck exit=1"
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Node.js (node + npx) is required to build the Slidev deck and was not found." >&2
  echo "Install Node.js 18+ from $node_install_url, then run:" >&2
  echo "  $slidev_npx_invocation" >&2
  echo "TOOL build-deck exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
npx --yes "$slidev_package" build "$slides_md" --out "$out_dir"
slidev_exit=$?
set -e

if [ "$slidev_exit" -ne 0 ]; then
  echo "Slidev build failed (exit $slidev_exit). To build manually run:" >&2
  echo "  $slidev_npx_invocation" >&2
  echo "TOOL build-deck exit=2"
  exit 2
fi

echo "TOOL build-deck exit=0"
