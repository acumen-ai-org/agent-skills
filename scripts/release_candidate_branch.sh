#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=${DRP_REPO:-.}
export DRP_REPO="$repo"
export DRP_CONFIG=${DRP_CONFIG:-$repo/dev-process.json}
cfg=$(python3 "$here/dev_process.py" emit) || { echo "dev-process: config invalid" >&2; exit 2; }
get() { printf '%s' "$cfg" | python3 -c 'import json,sys
d=json.load(sys.stdin)
for p in sys.argv[1].split("."):
    d = d[int(p)] if p.lstrip("-").isdigit() else d[p]
print("\n".join(str(x) for x in d) if isinstance(d,list) else ("" if d is None else d))' "$1"; }

main_branch=$(get branches.main)
release_candidate=$(python3 "$here/dev_process.py" value release-candidate-branch)

if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]; then
  echo "tracked changes are uncommitted; commit or stash before starting a release candidate" >&2
  exit 2
fi

git -C "$repo" fetch origin --prune || { echo "git fetch origin failed" >&2; exit 4; }

if ! git -C "$repo" rev-parse --verify --quiet "origin/$main_branch" >/dev/null; then
  echo "origin/$main_branch not found" >&2
  exit 2
fi

base=$(git -C "$repo" rev-parse "origin/$main_branch")
git -C "$repo" switch -C "$release_candidate" "origin/$main_branch" >/dev/null 2>&1
echo "release-candidate-branch=$release_candidate base=$base from=origin/$main_branch"
