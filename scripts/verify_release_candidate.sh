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
out_dir=$(get reports.outputDir)

git -C "$repo" fetch origin --prune || { echo "git fetch origin failed" >&2; exit 4; }
if ! git -C "$repo" rev-parse --verify --quiet "origin/$release_candidate" >/dev/null; then
  echo "origin/$release_candidate not found; build and push a release candidate first" >&2
  exit 2
fi

gate="$repo/$out_dir/_gate.json"
if [ ! -f "$gate" ]; then
  echo "analysis gate marker missing ($out_dir/_gate.json); run the analysis step" >&2
  exit 2
fi
if [ "$(GATE="$gate" python3 -c 'import json,os;print(json.load(open(os.environ["GATE"]))["gate"])')" != "pass" ]; then
  echo "analysis gate did not pass; see $out_dir/_gate.json" >&2
  exit 3
fi

echo "verify-release-candidate ok: origin/$release_candidate green, gate=pass"
