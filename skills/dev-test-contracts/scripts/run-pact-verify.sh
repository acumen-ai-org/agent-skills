#!/usr/bin/env bash
set -euo pipefail

provider_dir=${1:?usage: run-pact-verify.sh <provider-dir> <out_dir> <pacts-dir>}
out_dir=${2:?usage: run-pact-verify.sh <provider-dir> <out_dir> <pacts-dir>}
pacts_dir=${3:?usage: run-pact-verify.sh <provider-dir> <out_dir> <pacts-dir>}

pact_broker_image=pactfoundation/pact-broker:2.107.1-pactbroker1.97.3

if [ ! -d "$provider_dir" ]; then
  echo "provider directory not found: $provider_dir" >&2
  echo "TOOL run-pact-verify exit=5"
  exit 5
fi

if [ -z "${PACT_BROKER_BASE_URL:-}" ] && [ ! -d "$pacts_dir" ]; then
  echo "pacts directory not found and no PACT_BROKER_BASE_URL set: $pacts_dir" >&2
  echo "Provide a directory of consumer pact files, or export PACT_BROKER_BASE_URL." >&2
  echo "An ephemeral broker can be run with: docker run --rm -p 9292:9292 ${pact_broker_image}" >&2
  echo "TOOL run-pact-verify exit=5"
  exit 5
fi

mkdir -p "$out_dir"
result_json="$out_dir/pact-verify.raw.json"
verifier_log="$out_dir/pact-verify.log"

provider_stack=unknown
if [ -f "$provider_dir/package.json" ] && grep -Eq '"@pact-foundation/pact"' "$provider_dir/package.json"; then
  provider_stack=pact-js
elif find "$provider_dir" -maxdepth 2 -name '*.csproj' -print -quit 2>/dev/null | grep -q .; then
  provider_stack=pactnet
elif [ -f "$provider_dir/Cargo.toml" ] && grep -Eq '^pact_verifier|pact_verifier =' "$provider_dir/Cargo.toml"; then
  provider_stack=pact-rust
elif [ -f "$provider_dir/pyproject.toml" ] || [ -f "$provider_dir/setup.cfg" ] || [ -f "$provider_dir/setup.py" ] || find "$provider_dir" -maxdepth 2 -name 'requirements*.txt' -print -quit 2>/dev/null | grep -q .; then
  provider_stack=pact-python
elif [ -f "$provider_dir/package.json" ]; then
  provider_stack=pact-js
fi

instruct_missing() {
  missing_runtime=$1
  install_line=$2
  echo "Provider stack detected: ${provider_stack}." >&2
  echo "Required verifier runtime not found: ${missing_runtime}." >&2
  echo "Install it: ${install_line}" >&2
  echo "A Pact broker (optional, to serve consumer pacts) runs with:" >&2
  echo "  docker run --rm -p 9292:9292 ${pact_broker_image}" >&2
  echo "This script never auto-installs the verifier." >&2
  echo "TOOL run-pact-verify exit=3"
  exit 3
}

run_verifier() {
  set +e
  ( cd "$provider_dir" && "$@" ) >"$verifier_log" 2>&1
  verifier_code=$?
  set -e
}

case "$provider_stack" in
  pact-js)
    if ! command -v node >/dev/null 2>&1; then
      instruct_missing "node (pact-js verifier)" "https://nodejs.org/en/download + npm install @pact-foundation/pact"
    fi
    if [ ! -f "$provider_dir/package.json" ] || ! grep -Eq '"pact:verify"' "$provider_dir/package.json"; then
      echo "pact-js provider must expose an npm 'pact:verify' script that writes ${result_json}." >&2
      echo "It should run @pact-foundation/pact Verifier with verbose JSON output." >&2
      echo "TOOL run-pact-verify exit=3"
      exit 3
    fi
    PACT_VERIFY_OUTPUT="$result_json" PACT_VERIFY_PACTS_DIR="$pacts_dir" \
      run_verifier npm run --silent pact:verify
    ;;
  pactnet)
    if ! command -v dotnet >/dev/null 2>&1; then
      instruct_missing "dotnet (PactNet verifier)" "https://dotnet.microsoft.com/download + dotnet add package PactNet"
    fi
    PACT_VERIFY_OUTPUT="$result_json" PACT_VERIFY_PACTS_DIR="$pacts_dir" \
      run_verifier dotnet test --logger "trx;LogFileName=pact-verify.trx"
    ;;
  pact-python)
    if command -v pact-verifier >/dev/null 2>&1; then
      pact_python_runner=(pact-verifier)
    elif python3 -c 'import pact' >/dev/null 2>&1; then
      pact_python_runner=(python3 -m pact.verifier)
    else
      instruct_missing "pact-python (pact-verifier CLI or the 'pact' module)" "pip install pact-python"
    fi
    PACT_VERIFY_OUTPUT="$result_json" PACT_VERIFY_PACTS_DIR="$pacts_dir" \
      run_verifier "${pact_python_runner[@]}" --provider-base-url "${PACT_PROVIDER_BASE_URL:-http://localhost:8080}" --pact-dir "$pacts_dir"
    ;;
  pact-rust)
    if command -v pact_verifier_cli >/dev/null 2>&1; then
      pact_rust_runner=(pact_verifier_cli)
    elif command -v cargo >/dev/null 2>&1; then
      pact_rust_runner=(cargo test --quiet)
    else
      instruct_missing "pact-rust (pact_verifier_cli or cargo)" "cargo install pact_verifier_cli"
    fi
    PACT_VERIFY_OUTPUT="$result_json" PACT_VERIFY_PACTS_DIR="$pacts_dir" \
      run_verifier "${pact_rust_runner[@]}"
    ;;
  *)
    echo "could not determine the provider stack in: $provider_dir" >&2
    echo "Expected one of: package.json (pact-js), *.csproj (PactNet)," >&2
    echo "pyproject.toml/requirements*.txt (pact-python), Cargo.toml (pact-rust)." >&2
    echo "TOOL run-pact-verify exit=3"
    exit 3
    ;;
esac

if [ ! -s "$result_json" ]; then
  echo "verifier produced no result JSON at ${result_json}; raw log kept in ${verifier_log}" >&2
  echo "TOOL run-pact-verify exit=2"
  exit 2
fi

if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$result_json" >/dev/null 2>&1; then
  echo "verifier result is not valid JSON; raw kept at ${result_json}" >&2
  echo "TOOL run-pact-verify exit=2"
  exit 2
fi

failed_interactions=$(python3 - "$result_json" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))


def collect(node):
    found = []
    if isinstance(node, dict):
        for key in ("examples", "interactions", "verificationResults", "results"):
            value = node.get(key)
            if isinstance(value, list):
                found.extend(value)
        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(collect(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(collect(item))
    return found


def is_failure(item):
    if not isinstance(item, dict):
        return False
    status = str(item.get("status", item.get("status_text", ""))).lower()
    if status in ("failed", "failure", "error"):
        return True
    if item.get("success") is False:
        return True
    if item.get("mismatches"):
        return True
    if item.get("exception"):
        return True
    return False


print(sum(1 for item in collect(data) if is_failure(item)))
PY
)

if [ "$failed_interactions" -gt 0 ]; then
  echo "pact verification reported ${failed_interactions} failed interaction(s)" >&2
  echo "TOOL run-pact-verify exit=4"
  exit 4
fi

echo "TOOL run-pact-verify exit=0"
