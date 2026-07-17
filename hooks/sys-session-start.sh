#!/usr/bin/env bash
set -euo pipefail

dir=$(pwd)
while [ "$dir" != "/" ]; do
  if [ -f "$dir/sys.json" ]; then
    python3 - "$dir" <<'PY'
import json, sys, os
root = sys.argv[1]
cfg = json.load(open(os.path.join(root, "sys.json")))
canon = cfg.get("canon", ".")
if canon == ".":
    canon = root
print(f"""This repository follows the Acumen ways of working (sys.json present).
Canon: {canon}/docs/process/ (git workflow, release, definition of done, gates) and {canon}/system/docs/transparency.md (the required document set per level).
Report and doc freshness is governed by the acumen plugin's sys-sync skill: a Stop hook watches change volume and asks for a sync only after considerable changes — slightly stale docs are acceptable by design; do not update them for minor work. To adopt these conventions in another repo, use the sys-init skill.""")
PY
    exit 0
  fi
  dir=$(dirname "$dir")
done
exit 0
