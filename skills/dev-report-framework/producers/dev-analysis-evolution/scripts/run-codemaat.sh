#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: run-codemaat.sh <repo> <out_dir> <ref_range>}
out_dir=${2:?usage: run-codemaat.sh <repo> <out_dir> <ref_range>}
ref_range=${3:?usage: run-codemaat.sh <repo> <out_dir> <ref_range>}

codemaat_image=adamtornhill/code-maat:1.0

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL run-codemaat exit=5"
  exit 5
fi

range_left=${ref_range%%..*}
range_right=${ref_range##*..}
for endpoint in "$range_left" "$range_right"; do
  if [ -n "$endpoint" ] && ! git -C "$repo" rev-parse --verify --quiet "$endpoint^{commit}" >/dev/null; then
    echo "ref not found in $repo: $endpoint" >&2
    echo "TOOL run-codemaat exit=5"
    exit 5
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to run code-maat and was not found on PATH." >&2
  echo "Install Docker: https://docs.docker.com/engine/install/" >&2
  echo "Then this script runs: docker run --rm -v <out_dir>:/data ${codemaat_image} -l /data/codemaat-log.txt -c git2 -a <analysis>" >&2
  echo "TOOL run-codemaat exit=3"
  exit 3
fi

mkdir -p "$out_dir"
log_path="$out_dir/codemaat-log.txt"

git -C "$repo" log "$ref_range" --no-merges --date=short \
  --pretty=format:'--%h--%ad--%aN' --numstat >"$log_path"

abs_out_dir=$(cd "$out_dir" && pwd)
analyses=(abs-churn coupling entity-ownership)
declare -A analysis_file=(
  [abs-churn]=codemaat-churn.csv
  [coupling]=codemaat-coupling.csv
  [entity-ownership]=codemaat-ownership.csv
)

overall_exit=0
for analysis in "${analyses[@]}"; do
  output_file=${analysis_file[$analysis]}
  set +e
  docker run --rm -v "$abs_out_dir:/data" "$codemaat_image" \
    -l /data/codemaat-log.txt -c git2 -a "$analysis" \
    >"$abs_out_dir/$output_file" 2>"$abs_out_dir/$output_file.err"
  docker_code=$?
  set -e
  if [ "$docker_code" -ne 0 ]; then
    overall_exit=2
  fi
done

if [ "$overall_exit" -eq 2 ]; then
  echo "code-maat produced no parseable CSV; raw kept in $out_dir" >&2
  echo "TOOL run-codemaat exit=2"
  exit 2
fi

echo "TOOL run-codemaat exit=0"
