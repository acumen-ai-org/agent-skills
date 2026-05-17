#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: run-difftastic.sh <repo> <out_dir> <ref_range>}
out_dir=${2:?usage: run-difftastic.sh <repo> <out_dir> <ref_range>}
ref_range=${3:?usage: run-difftastic.sh <repo> <out_dir> <ref_range>}

difftastic_image=ghcr.io/wilfred/difftastic:0.62.0

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL run-difftastic exit=5"
  exit 5
fi

range_left=${ref_range%%..*}
range_right=${ref_range##*..}
if [ "$range_left" = "$ref_range" ] || [ "$range_right" = "$ref_range" ]; then
  echo "ref_range must be <ref>..<ref>, got: $ref_range" >&2
  echo "TOOL run-difftastic exit=5"
  exit 5
fi
for ref in "$range_left" "$range_right"; do
  if ! git -C "$repo" rev-parse --verify --quiet "$ref^{commit}" >/dev/null; then
    echo "ref not found in $repo: $ref" >&2
    echo "TOOL run-difftastic exit=5"
    exit 5
  fi
done

mkdir -p "$out_dir"
raw_path="$out_dir/difftastic.raw.txt"
repo_abs=$(cd "$repo" && pwd)

run_difftastic() {
  if command -v difft >/dev/null 2>&1; then
    GIT_EXTERNAL_DIFF=difft git -C "$repo_abs" --no-pager diff --ext-diff "$range_left" "$range_right" >"$raw_path"
    return $?
  fi
  if command -v docker >/dev/null 2>&1; then
    git -C "$repo_abs" --no-pager diff --name-only "$range_left" "$range_right" >"$out_dir/difftastic.files.txt"
    : >"$raw_path"
    while IFS= read -r changed; do
      [ -n "$changed" ] || continue
      old_blob=$(git -C "$repo_abs" show "$range_left:$changed" 2>/dev/null || true)
      new_blob=$(git -C "$repo_abs" show "$range_right:$changed" 2>/dev/null || true)
      tmp_old=$(mktemp)
      tmp_new=$(mktemp)
      printf '%s' "$old_blob" >"$tmp_old"
      printf '%s' "$new_blob" >"$tmp_new"
      {
        echo "=== $changed ==="
        docker run --rm \
          -v "$tmp_old:/a:ro" \
          -v "$tmp_new:/b:ro" \
          "$difftastic_image" /a /b || true
      } >>"$raw_path"
      rm -f "$tmp_old" "$tmp_new"
    done <"$out_dir/difftastic.files.txt"
    return 0
  fi
  echo "difftastic (difft) not found and Docker not available." >&2
  echo "Install difftastic: cargo install difftastic" >&2
  echo "Or run via Docker:  docker run --rm -v \"<old>:/a:ro\" -v \"<new>:/b:ro\" $difftastic_image /a /b" >&2
  echo "TOOL run-difftastic exit=3"
  exit 3
}

set +e
run_difftastic
tool_code=$?
set -e

if [ ! -f "$raw_path" ]; then
  echo "difftastic produced no output (exit $tool_code)" >&2
  echo "TOOL run-difftastic exit=2"
  exit 2
fi

echo "TOOL run-difftastic exit=0"
