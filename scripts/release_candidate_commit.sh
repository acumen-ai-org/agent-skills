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

release_candidate=$(python3 "$here/dev_process.py" value release-candidate-branch)
release=$(python3 "$here/dev_process.py" value release-id)
cur=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
if [ "$cur" != "$release_candidate" ]; then
  echo "on '$cur', expected release-candidate branch '$release_candidate'" >&2
  exit 2
fi

paths=("$(get releaseNotes.path)" "$(get releaseNotes.changelogPath)")

added=0
for p in "${paths[@]}"; do
  [ -n "$p" ] && [ -e "$repo/$p" ] && git -C "$repo" add -- "$p" && added=1
done
if [ "$added" -eq 0 ] || git -C "$repo" diff --cached --quiet; then
  echo "release-candidate commit: nothing to commit (no configured artifacts changed)"
  exit 0
fi
git -C "$repo" commit -q -m "release-candidate: $release"
echo "release-candidate commit $(git -C "$repo" rev-parse --short HEAD) on $release_candidate"
