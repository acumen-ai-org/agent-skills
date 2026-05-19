#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-msadoc.sh <solution-or-project-dir> <out_dir>}
out_dir=${2:?usage: run-msadoc.sh <solution-or-project-dir> <out_dir>}

fragment_id=architecture-msadoc
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
msadoc_tool_package="MsaDoc.Cli"

if [ ! -d "$target" ]; then
  echo "target is not a directory: $target" >&2
  echo "TOOL msadoc exit=5"
  exit 5
fi

if ! command -v dotnet >/dev/null 2>&1; then
  echo "MSADoc requires the .NET SDK. It is not installed and is never auto-installed." >&2
  echo "Install the .NET SDK from https://dotnet.microsoft.com/download then generate the service catalog:" >&2
  echo "  dotnet tool install --global ${msadoc_tool_package}" >&2
  echo "  msadoc extract --solution '${target}' --output '${raw_path}'" >&2
  echo "TOOL msadoc exit=3"
  exit 3
fi

if ! dotnet tool list --global 2>/dev/null | grep -qi "msadoc"; then
  echo "MSADoc .NET tool not found on this machine. It is never auto-installed." >&2
  echo "Install it once, then re-run this script:" >&2
  echo "  dotnet tool install --global ${msadoc_tool_package}" >&2
  echo "TOOL msadoc exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
msadoc extract --solution "$target" --output "$raw_path" \
  >"${out_dir}/${fragment_id}.stdout.log" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

if [ ! -s "$raw_path" ]; then
  echo "MSADoc produced no catalog (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL msadoc exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL msadoc exit=${fragment_status}"
exit "$fragment_status"
