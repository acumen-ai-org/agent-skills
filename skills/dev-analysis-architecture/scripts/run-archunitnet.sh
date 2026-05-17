#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-archunitnet.sh <arch-test-project-dir> <out_dir>}
out_dir=${2:?usage: run-archunitnet.sh <arch-test-project-dir> <out_dir>}

fragment_id=architecture-archunitnet
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
archunitnet_nuget_package="TngTech.ArchUnitNET.xUnit"

if [ ! -d "$target" ]; then
  echo "target is not a directory: $target" >&2
  echo "TOOL archunitnet exit=5"
  exit 5
fi

if ! command -v dotnet >/dev/null 2>&1; then
  echo "ArchUnitNET/NetArchTest run as a .NET test project. The .NET SDK is not installed and is never auto-installed." >&2
  echo "Install the .NET SDK from https://dotnet.microsoft.com/download, add the rule package to an xUnit project:" >&2
  echo "  dotnet add '${target}' package ${archunitnet_nuget_package}" >&2
  echo "then run the layering rules as tests with a TRX log:" >&2
  echo "  dotnet test '${target}' --logger 'trx;LogFileName=archunitnet.trx' --results-directory '${out_dir}'" >&2
  echo "F# limitation: ArchUnitNET/NetArchTest reflect over compiled CLR metadata; F# modules/functions map poorly." >&2
  echo "For F# components, model the architecture with a Structurizr DSL and run scripts/run-structurizr.sh instead." >&2
  echo "TOOL archunitnet exit=3"
  exit 3
fi

mkdir -p "$out_dir"

set +e
dotnet test "$target" \
  --logger "trx;LogFileName=archunitnet.trx" \
  --results-directory "$out_dir" \
  >"${out_dir}/${fragment_id}.stdout.log" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

trx_path="${out_dir}/archunitnet.trx"
if [ ! -s "$trx_path" ]; then
  echo "dotnet test produced no TRX result (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL archunitnet exit=2"
  exit 2
fi

python3 - "$trx_path" "$raw_path" <<'PY'
import json
import sys
import xml.etree.ElementTree as ET

trx_path, raw_path = sys.argv[1], sys.argv[2]
namespace = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
tree = ET.parse(trx_path)
root = tree.getroot()
results = []
for unit in root.findall(".//t:UnitTestResult", namespace):
    outcome = (unit.get("outcome") or "").lower()
    name = unit.get("testName") or "rule"
    message = ""
    message_node = unit.find(".//t:Message", namespace)
    if message_node is not None and message_node.text:
        message = message_node.text.strip()
    results.append(
        {
            "rule": name,
            "outcome": "failed" if outcome == "failed" else "passed",
            "message": message,
        }
    )
with open(raw_path, "w", encoding="utf-8") as handle:
    json.dump({"results": results}, handle)
PY

if [ ! -s "$raw_path" ]; then
  echo "could not normalize TRX into rule results" >&2
  echo "TOOL archunitnet exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL archunitnet exit=${fragment_status}"
exit "$fragment_status"
