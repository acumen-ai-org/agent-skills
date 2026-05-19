#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: run-cargo-geiger.sh <target> <out_dir> [id]" >&2
  echo "  <target>   Rust crate/workspace directory with a Cargo.toml" >&2
  echo "  <out_dir>  directory for <id>.cargo-geiger.raw.json" >&2
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
  echo "TOOL cargo-geiger exit=5" >&2
  exit 5
fi

if [ ! -f "${target}/Cargo.toml" ]; then
  echo "no Cargo.toml in ${target}; cargo-geiger needs a cargo project" >&2
  echo "TOOL cargo-geiger exit=5" >&2
  exit 5
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo is required to run cargo-geiger and was not found." >&2
  echo "Install the Rust toolchain: https://rustup.rs" >&2
  echo "Then install the subcommand: cargo install cargo-geiger --locked" >&2
  echo "TOOL cargo-geiger exit=3" >&2
  exit 3
fi

if ! cargo geiger --version >/dev/null 2>&1; then
  echo "cargo-geiger subcommand not installed." >&2
  echo "Install it: cargo install cargo-geiger --locked" >&2
  echo "TOOL cargo-geiger exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
out_abs=$(realpath "$out_dir")
raw_path="${out_abs}/${fragment_id}.cargo-geiger.raw.json"

set +e
( cd "$target" && cargo geiger --output-format Json --quiet ) >"$raw_path" 2>/dev/null
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "cargo-geiger produced no JSON (exit ${tool_status}); raw kept at ${raw_path}" >&2
  echo "TOOL cargo-geiger exit=2" >&2
  exit 2
fi

echo "wrote ${raw_path}"
echo "TOOL cargo-geiger exit=0"
