#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-cargo-modules.sh <crate-dir> <out_dir>}
out_dir=${2:?usage: run-cargo-modules.sh <crate-dir> <out_dir>}

fragment_id=architecture-cargo-modules
raw_path="${out_dir}/${fragment_id}.raw.dot"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cargo_modules_crate="cargo-modules"

if [ ! -f "${target}/Cargo.toml" ]; then
  echo "no Cargo.toml in ${target}; not a crate" >&2
  echo "TOOL cargo-modules exit=5"
  exit 5
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo-modules requires the Rust toolchain (cargo). It is not installed and is never auto-installed." >&2
  echo "Install Rust from https://rustup.rs then add and run cargo-modules:" >&2
  echo "  cargo install ${cargo_modules_crate}" >&2
  echo "  (cd '${target}' && cargo modules dependencies --no-externs --no-fns --no-traits --no-types) > '${raw_path}'" >&2
  echo "TOOL cargo-modules exit=3"
  exit 3
fi

if ! cargo modules --version >/dev/null 2>&1; then
  echo "cargo subcommand 'modules' not found. It is never auto-installed." >&2
  echo "Install it once, then re-run this script:" >&2
  echo "  cargo install ${cargo_modules_crate}" >&2
  echo "TOOL cargo-modules exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
( cd "$target" && cargo modules dependencies --no-externs --no-fns --no-traits --no-types ) \
  >"$raw_path" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "cargo-modules produced no graph (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL cargo-modules exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL cargo-modules exit=${fragment_status}"
exit "$fragment_status"
