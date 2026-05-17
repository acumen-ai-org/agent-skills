#!/usr/bin/env bash
set -euo pipefail

repo=${1:?usage: run-git-of-theseus.sh <repo> <out_dir>}
out_dir=${2:?usage: run-git-of-theseus.sh <repo> <out_dir>}

git_of_theseus_pip_package=git-of-theseus

if ! git -C "$repo" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository: $repo" >&2
  echo "TOOL run-git-of-theseus exit=5"
  exit 5
fi

if ! command -v git-of-theseus-analyze >/dev/null 2>&1; then
  echo "git-of-theseus-analyze was not found on PATH." >&2
  echo "Install it: pip install ${git_of_theseus_pip_package}" >&2
  echo "git-of-theseus is a pip package, not Docker-wrapped; this script never installs it." >&2
  echo "TOOL run-git-of-theseus exit=3"
  exit 3
fi

mkdir -p "$out_dir"
abs_out_dir=$(cd "$out_dir" && pwd)
abs_repo=$(cd "$repo" && pwd)

set +e
git-of-theseus-analyze "$abs_repo" --outdir "$abs_out_dir" \
  >"$abs_out_dir/git-of-theseus-stdout.txt" 2>&1
analyze_code=$?
set -e

cohorts_path="$abs_out_dir/cohorts.json"
survival_path="$abs_out_dir/survival.json"

if [ "$analyze_code" -ne 0 ] || { [ ! -f "$cohorts_path" ] && [ ! -f "$survival_path" ]; }; then
  echo "git-of-theseus-analyze produced no cohort/survival JSON; raw kept in $out_dir" >&2
  echo "TOOL run-git-of-theseus exit=2"
  exit 2
fi

echo "TOOL run-git-of-theseus exit=0"
