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
prod=$(get branches.production)
strategy=$(get scope.productionRef.strategy)
tag_pattern=$(get scope.productionRef.tagPattern)
commit=$(get scope.productionRef.commit)
out_dir=$(get reports.outputDir)
mapfile -t fallback < <(get scope.fallbackOrder)
mapfile -t pathspec < <(get scope.changedFilesPathspec)

git -C "$repo" fetch origin --prune --tags || { echo "git fetch origin failed" >&2; exit 4; }

if ! git -C "$repo" rev-parse --verify --quiet "origin/$main_branch" >/dev/null; then
  echo "origin/$main_branch not found" >&2
  exit 2
fi
to_sha=$(git -C "$repo" rev-parse "origin/$main_branch")

resolve() {
  case "$1" in
    branch) git -C "$repo" rev-parse --verify --quiet "origin/$prod" || return 1 ;;
    tag) t=$(git -C "$repo" describe --tags --abbrev=0 --match "$tag_pattern" "$to_sha" 2>/dev/null) && git -C "$repo" rev-parse "$t" || return 1 ;;
    commit) [ -n "$commit" ] && git -C "$repo" rev-parse --verify --quiet "$commit" || return 1 ;;
    root) git -C "$repo" rev-list --max-parents=0 "$to_sha" | tail -1 ;;
  esac
}

from_sha=""
used=""
for s in "$strategy" "${fallback[@]}"; do
  if from_sha=$(resolve "$s"); then used="$s"; break; fi
done
if [ -z "$from_sha" ]; then
  echo "could not resolve a production endpoint (strategy=$strategy, fallback=${fallback[*]})" >&2
  exit 2
fi
[ "$used" = "root" ] && echo "warning: scope endpoint fell back to repository root; whole history is in scope" >&2

range="$from_sha..$to_sha"
mkdir -p "$repo/$out_dir"
git -C "$repo" log --no-merges --pretty='%H%x09%s' "$range" > "$repo/$out_dir/commits.txt"
count=$(wc -l < "$repo/$out_dir/commits.txt" | tr -d ' ')
if [ "${#pathspec[@]}" -gt 0 ] && [ -n "${pathspec[0]}" ]; then
  git -C "$repo" diff --name-status "$range" -- "${pathspec[@]}" > "$repo/$out_dir/changed-files.txt"
else
  git -C "$repo" diff --name-status "$range" > "$repo/$out_dir/changed-files.txt"
fi

FROM="$from_sha" TO="$to_sha" RANGE="$range" USED="$used" COUNT="$count" \
python3 -c 'import json,os
print(json.dumps({"from":os.environ["FROM"],"to":os.environ["TO"],"range":os.environ["RANGE"],"endpointStrategy":os.environ["USED"],"commitCount":int(os.environ["COUNT"])},indent=2))' \
> "$repo/$out_dir/scope.json"
echo "scope $range ($count commits, endpoint=$used) -> $out_dir/scope.json"
