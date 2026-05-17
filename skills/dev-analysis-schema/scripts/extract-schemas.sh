#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: extract-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
out_dir=${2:?usage: extract-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
ref_a=${3:?usage: extract-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
ref_b=${4:?usage: extract-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}

if [ ! -d "$repo/.git" ]; then
  echo "not a git repository: $repo" >&2
  echo "TOOL extract-schemas exit=5"
  exit 5
fi

git -C "$repo" rev-parse --verify --quiet "$ref_a^{commit}" >/dev/null || {
  echo "ref not found: $ref_a" >&2
  echo "TOOL extract-schemas exit=5"
  exit 5
}
git -C "$repo" rev-parse --verify --quiet "$ref_b^{commit}" >/dev/null || {
  echo "ref not found: $ref_b" >&2
  echo "TOOL extract-schemas exit=5"
  exit 5
}

openapi_json_path_regex='(^|/)(openapi|swagger)[^/]*\.json$'
openapi_yaml_path_regex='(^|/)(openapi|swagger)[^/]*\.ya?ml$'
graphql_path_regex='\.(graphql|gql|graphqls)$'
mcp_path_regex='(^|/)(mcp|tools|resources)[^/]*\.json$'

mkdir -p "$out_dir"

extract_ref_into() {
  ref_name=$1
  side_dir=$2
  mkdir -p "$side_dir/openapi" "$side_dir/graphql" "$side_dir/mcp"

  git -C "$repo" ls-tree -r --name-only "$ref_name" | while IFS= read -r tracked_path; do
    flat_name=$(printf '%s' "$tracked_path" | tr '/' '__')
    if printf '%s' "$tracked_path" | grep -Eiq "$openapi_json_path_regex"; then
      git -C "$repo" show "$ref_name:$tracked_path" > "$side_dir/openapi/$flat_name"
    elif printf '%s' "$tracked_path" | grep -Eiq "$openapi_yaml_path_regex"; then
      git -C "$repo" show "$ref_name:$tracked_path" > "$side_dir/openapi/$flat_name"
    elif printf '%s' "$tracked_path" | grep -Eiq "$graphql_path_regex"; then
      git -C "$repo" show "$ref_name:$tracked_path" > "$side_dir/graphql/$flat_name"
    elif printf '%s' "$tracked_path" | grep -Eiq "$mcp_path_regex"; then
      git -C "$repo" show "$ref_name:$tracked_path" > "$side_dir/mcp/$flat_name"
    fi
  done
}

extract_ref_into "$ref_a" "$out_dir/ref_a"
extract_ref_into "$ref_b" "$out_dir/ref_b"

openapi_a=$(find "$out_dir/ref_a/openapi" -type f 2>/dev/null | wc -l | tr -d ' ')
openapi_b=$(find "$out_dir/ref_b/openapi" -type f 2>/dev/null | wc -l | tr -d ' ')
graphql_a=$(find "$out_dir/ref_a/graphql" -type f 2>/dev/null | wc -l | tr -d ' ')
graphql_b=$(find "$out_dir/ref_b/graphql" -type f 2>/dev/null | wc -l | tr -d ' ')
mcp_a=$(find "$out_dir/ref_a/mcp" -type f 2>/dev/null | wc -l | tr -d ' ')
mcp_b=$(find "$out_dir/ref_b/mcp" -type f 2>/dev/null | wc -l | tr -d ' ')

python3 - "$out_dir/extract-manifest.json" \
  "$ref_a" "$ref_b" \
  "$openapi_a" "$openapi_b" "$graphql_a" "$graphql_b" "$mcp_a" "$mcp_b" <<'PY'
import json, sys
out, ref_a, ref_b = sys.argv[1], sys.argv[2], sys.argv[3]
oa, ob, ga, gb, ma, mb = (int(x) for x in sys.argv[4:10])
manifest = {
    "ref_a": ref_a,
    "ref_b": ref_b,
    "counts": {
        "openapi": {"ref_a": oa, "ref_b": ob},
        "graphql": {"ref_a": ga, "ref_b": gb},
        "mcp": {"ref_a": ma, "ref_b": mb},
    },
}
with open(out, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2, sort_keys=True)
PY

echo "TOOL extract-schemas exit=0"
