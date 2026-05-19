#!/usr/bin/env bash
set -euo pipefail

target=${1:?usage: run-structurizr.sh <workspace.dsl> <out_dir>}
out_dir=${2:?usage: run-structurizr.sh <workspace.dsl> <out_dir>}

fragment_id=architecture-structurizr
raw_path="${out_dir}/${fragment_id}.raw.json"
fragment_path="${out_dir}/${fragment_id}.fragment.json"
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
structurizr_cli_image="structurizr/cli:2024.07.02"
structurizr_lite_image="structurizr/lite:2024.07.02"

if [ ! -f "$target" ]; then
  echo "workspace DSL not found: $target" >&2
  echo "TOOL structurizr exit=5"
  exit 5
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Structurizr CLI runs via its official Docker image. Docker is not installed and is never auto-installed." >&2
  echo "Install Docker from https://docs.docker.com/get-docker/ then export the workspace to JSON:" >&2
  echo "  docker run --rm -v \"\$(dirname '${target}')\":/ws ${structurizr_cli_image} export -workspace \"/ws/\$(basename '${target}')\" -format json -output /ws" >&2
  echo "For the interactive C4 view instead of an export:" >&2
  echo "  docker run --rm -p 8080:8080 -v \"\$(dirname '${target}')\":/usr/local/structurizr ${structurizr_lite_image}" >&2
  echo "TOOL structurizr exit=3"
  exit 3
fi

mkdir -p "$out_dir"
workspace_dir=$(cd "$(dirname "$target")" && pwd)
workspace_file=$(basename "$target")

set +e
docker run --rm -v "${workspace_dir}:/ws" "$structurizr_cli_image" \
  export -workspace "/ws/${workspace_file}" -format json -output /ws \
  >"${out_dir}/${fragment_id}.stdout.log" 2>"${out_dir}/${fragment_id}.stderr.log"
tool_status=$?
set -e

exported_json=$(ls -1 "${workspace_dir}"/*.json 2>/dev/null | head -n1 || true)
if [ -n "$exported_json" ] && [ -s "$exported_json" ]; then
  cp "$exported_json" "$raw_path"
fi

if [ ! -s "$raw_path" ]; then
  echo "Structurizr export produced no JSON (exit ${tool_status}); see ${out_dir}/${fragment_id}.stderr.log" >&2
  echo "TOOL structurizr exit=2"
  exit 2
fi

python3 "${script_dir}/to-fragment.py" "$fragment_id" "$raw_path" "$fragment_path"
fragment_status=$?

echo "TOOL structurizr exit=${fragment_status}"
exit "$fragment_status"
