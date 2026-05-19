#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-codeql.sh <target> <out_dir> <language>}
out_dir=${2:?usage: run-codeql.sh <target> <out_dir> <language>}
language=${3:?usage: run-codeql.sh <target> <out_dir> <language>}

codeql_image=ghcr.io/github/codeql-action/codeql-runner:latest

if [ "${CODEQL_LICENSE_ACK:-}" != "true" ]; then
  echo "CodeQL is licensing-gated and never on the default path." >&2
  echo "Read skills/dev-analysis-quality/references/codeql-optional.md and, only" >&2
  echo "where the CodeQL license permits, re-run with CODEQL_LICENSE_ACK=true." >&2
  echo "TOOL run-codeql exit=3"
  exit 3
fi

if [ ! -e "$target" ]; then
  echo "target does not exist: $target" >&2
  echo "TOOL run-codeql exit=5"
  exit 5
fi

mkdir -p "$out_dir"
raw_path="$out_dir/codeql.raw.sarif"
target_abs=$(cd "$(dirname "$target")" && pwd)/$(basename "$target")
out_abs=$(cd "$out_dir" && pwd)
db_dir="$out_abs/codeql-db"

run_codeql() {
  if command -v codeql >/dev/null 2>&1; then
    codeql database create "$db_dir" --language "$language" --source-root "$target_abs" --overwrite
    codeql database analyze "$db_dir" --format sarif-latest --output "$raw_path" --download
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    docker run --rm \
      -v "$target_abs:/src:ro" \
      -v "$out_abs:/out" \
      "$codeql_image" \
      codeql database create /out/codeql-db --language "$language" --source-root /src --overwrite
    docker run --rm \
      -v "$out_abs:/out" \
      "$codeql_image" \
      codeql database analyze /out/codeql-db --format sarif-latest --output /out/codeql.raw.sarif --download
    return $?
  fi
  echo "codeql not found and Docker not available." >&2
  echo "Install CodeQL CLI: see https://docs.github.com/en/code-security/codeql-cli" >&2
  echo "Or run via Docker:  docker run --rm -v \"$target_abs:/src:ro\" -v \"$out_abs:/out\" $codeql_image codeql database create /out/codeql-db --language $language --source-root /src --overwrite" >&2
  echo "TOOL run-codeql exit=3"
  exit 3
}

set +e
run_codeql
tool_code=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "codeql produced no output (exit $tool_code)" >&2
  echo "TOOL run-codeql exit=2"
  exit 2
fi

if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$raw_path" >/dev/null 2>&1; then
  echo "codeql SARIF is not valid JSON; kept at $raw_path" >&2
  echo "TOOL run-codeql exit=2"
  exit 2
fi

echo "TOOL run-codeql exit=0"
