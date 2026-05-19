#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: run-cargo-audit.sh <target> <out_dir> [id]" >&2
  echo "  <target>   Rust crate/workspace directory containing Cargo.lock" >&2
  echo "  <out_dir>  directory for <id>.cargo-audit.raw.json" >&2
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
  echo "TOOL cargo-audit exit=5" >&2
  exit 5
fi

if [ ! -f "${target}/Cargo.lock" ]; then
  echo "no Cargo.lock in ${target}; cargo-audit needs a resolved lockfile" >&2
  echo "TOOL cargo-audit exit=5" >&2
  exit 5
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo is required to run cargo-audit and was not found." >&2
  echo "Install the Rust toolchain: https://rustup.rs" >&2
  echo "Then install the subcommand: cargo install cargo-audit --locked" >&2
  echo "TOOL cargo-audit exit=3" >&2
  exit 3
fi

if ! cargo audit --version >/dev/null 2>&1; then
  echo "cargo-audit subcommand not installed." >&2
  echo "Install it: cargo install cargo-audit --locked" >&2
  echo "TOOL cargo-audit exit=3" >&2
  exit 3
fi

mkdir -p "$out_dir"
out_abs=$(realpath "$out_dir")
raw_path="${out_abs}/${fragment_id}.cargo-audit.raw.json"

set +e
( cd "$target" && cargo audit --json ) >"$raw_path" 2>/dev/null
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "cargo-audit produced no JSON (exit ${tool_status}); raw kept at ${raw_path}" >&2
  echo "TOOL cargo-audit exit=2" >&2
  exit 2
fi

echo "wrote ${raw_path}"
echo "TOOL cargo-audit exit=0"
