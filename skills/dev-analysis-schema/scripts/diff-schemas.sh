#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: diff-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
out_dir=${2:?usage: diff-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
ref_a=${3:?usage: diff-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}
ref_b=${4:?usage: diff-schemas.sh <repo> <out_dir> <ref_a> <ref_b>}

script_dir=$(cd "$(dirname "$0")" && pwd)

bash "$script_dir/extract-schemas.sh" "$repo" "$out_dir" "$ref_a" "$ref_b"

mkdir -p "$out_dir/openapi-diff" "$out_dir/graphql-diff" "$out_dir/mcp-diff" \
  "$out_dir/classified/ref_a" "$out_dir/classified/ref_b"

tool_missing=0

for side in ref_a ref_b; do
  for spec in "$out_dir/$side/openapi"/*; do
    [ -e "$spec" ] || continue
    case "$spec" in
      *.json)
        python3 "$script_dir/classify-endpoints.py" \
          "$spec" "$out_dir/classified/$side" || true
        ;;
      *)
        ;;
    esac
  done
done

run_oasdiff_pair() {
  visibility=$1
  base_spec=$2
  revision_spec=$3
  raw_out=$4
  if [ ! -f "$base_spec" ] || [ ! -f "$revision_spec" ]; then
    printf '%s\n' '{"breakingChanges":[]}' > "$raw_out"
    return 0
  fi
  set +e
  bash "$script_dir/run-oasdiff.sh" "$base_spec" "$revision_spec" "$raw_out"
  oasdiff_exit=$?
  set -e
  if [ "$oasdiff_exit" -eq 3 ]; then
    tool_missing=1
    printf '%s\n' '{"breakingChanges":[],"toolMissing":true}' > "$raw_out"
  fi
  return 0
}

for base_public in "$out_dir/classified/ref_a"/*.public.json; do
  [ -e "$base_public" ] || continue
  stem=$(basename "$base_public" .public.json)
  revision_public="$out_dir/classified/ref_b/$stem.public.json"
  revision_private="$out_dir/classified/ref_b/$stem.private.json"
  base_private="$out_dir/classified/ref_a/$stem.private.json"
  run_oasdiff_pair public "$base_public" "$revision_public" \
    "$out_dir/openapi-diff/$stem.public.json"
  run_oasdiff_pair private "$base_private" "$revision_private" \
    "$out_dir/openapi-diff/$stem.private.json"
done

graphql_base=$(find "$out_dir/ref_a/graphql" -type f 2>/dev/null | head -n 1 || true)
graphql_revision=$(find "$out_dir/ref_b/graphql" -type f 2>/dev/null | head -n 1 || true)
if [ -n "$graphql_base" ] && [ -n "$graphql_revision" ]; then
  set +e
  bash "$script_dir/run-graphql-inspector.sh" \
    "$graphql_base" "$graphql_revision" \
    "$out_dir/graphql-diff/schema.json"
  graphql_exit=$?
  set -e
  if [ "$graphql_exit" -eq 3 ]; then
    tool_missing=1
    printf '%s\n' '{"changes":[],"toolMissing":true}' > "$out_dir/graphql-diff/schema.json"
  fi
else
  printf '%s\n' '{"changes":[]}' > "$out_dir/graphql-diff/schema.json"
fi

python3 "$script_dir/mcp-schema-diff.py" \
  "$out_dir/ref_a/mcp" "$out_dir/ref_b/mcp" \
  "$out_dir/mcp-diff/schema.json"

python3 - "$out_dir" "$ref_a" "$ref_b" "$tool_missing" <<'PY'
import json, pathlib, sys

out_dir = pathlib.Path(sys.argv[1])
ref_a, ref_b = sys.argv[2], sys.argv[3]
tool_missing = sys.argv[4] == "1"

merged = {
    "ref_a": ref_a,
    "ref_b": ref_b,
    "toolMissing": tool_missing,
    "openapi": {"public": [], "private": []},
    "graphql": [],
    "mcp": [],
}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def oasdiff_breaking(document):
    if isinstance(document, dict):
        for key in ("breakingChanges", "BreakingChanges", "breaking_changes"):
            value = document.get(key)
            if isinstance(value, list):
                return value
        if isinstance(document.get("changes"), list):
            return [c for c in document["changes"] if isinstance(c, dict)]
    if isinstance(document, list):
        return document
    return []


for diff_path in sorted((out_dir / "openapi-diff").glob("*.public.json")):
    for change in oasdiff_breaking(read_json(diff_path)):
        merged["openapi"]["public"].append(change)
for diff_path in sorted((out_dir / "openapi-diff").glob("*.private.json")):
    for change in oasdiff_breaking(read_json(diff_path)):
        merged["openapi"]["private"].append(change)

graphql_doc = read_json(out_dir / "graphql-diff" / "schema.json")
if isinstance(graphql_doc, dict) and isinstance(graphql_doc.get("changes"), list):
    merged["graphql"] = graphql_doc["changes"]

mcp_doc = read_json(out_dir / "mcp-diff" / "schema.json")
if isinstance(mcp_doc, dict) and isinstance(mcp_doc.get("changes"), list):
    merged["mcp"] = mcp_doc["changes"]

public_breaking = len(merged["openapi"]["public"]) + sum(
    1 for c in merged["graphql"]
    if isinstance(c, dict) and str(c.get("criticality", "")).upper() == "BREAKING"
) + sum(
    1 for c in merged["mcp"]
    if isinstance(c, dict) and str(c.get("criticality", "")).upper() == "BREAKING"
)
private_breaking = len(merged["openapi"]["private"])

total_changes = (
    len(merged["openapi"]["public"])
    + len(merged["openapi"]["private"])
    + len(merged["graphql"])
    + len(merged["mcp"])
)

merged["summary"] = {
    "hasDiff": total_changes > 0,
    "publicBreaking": public_breaking,
    "privateBreaking": private_breaking,
    "totalChanges": total_changes,
}

(out_dir / "schema-diff.json").write_text(
    json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
)
print(
    "DIFF hasDiff={} publicBreaking={} privateBreaking={} total={}".format(
        merged["summary"]["hasDiff"],
        public_breaking,
        private_breaking,
        total_changes,
    )
)
PY

echo "TOOL diff-schemas exit=0"
