#!/usr/bin/env bash
set -euo pipefail

input=$(cat || true)

dir=$(pwd)
root=""
while [ "$dir" != "/" ]; do
  if [ -f "$dir/sys.json" ]; then root="$dir"; break; fi
  dir=$(dirname "$dir")
done
[ -z "$root" ] && exit 0
git -C "$root" rev-parse --git-dir >/dev/null 2>&1 || exit 0

export SYS_HOOK_INPUT="$input"
python3 - "$root" <<'PY' || exit 0
import json, os, subprocess, sys, fnmatch

root = sys.argv[1]
stdin = os.environ.get("SYS_HOOK_INPUT", "")
try:
    payload = json.loads(stdin) if stdin.strip() else {}
except json.JSONDecodeError:
    payload = {}
if payload.get("stop_hook_active"):
    sys.exit(0)

cfg = json.load(open(os.path.join(root, "sys.json")))
threshold = cfg.get("threshold", 300)
cooldown = cfg.get("cooldown", 10)
watch = cfg.get("watch", ["**"])
exclude = cfg.get("exclude", [])

state_dir = os.path.join(root, ".ai")
state_path = os.path.join(state_dir, "sys-sync-state.json")
os.makedirs(state_dir, exist_ok=True)
try:
    state = json.load(open(state_path))
except (FileNotFoundError, json.JSONDecodeError):
    state = {}

def git(*args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True).stdout

head = git("rev-parse", "HEAD").strip()
if not head:
    sys.exit(0)

if "lastSyncCommit" not in state or not git("cat-file", "-t", state["lastSyncCommit"]).strip() == "commit":
    state = {"lastSyncCommit": head, "turnsSinceTrigger": cooldown}
    json.dump(state, open(state_path, "w"), indent=2)
    sys.exit(0)

def matches(path):
    if any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g + "/**") for g in exclude):
        return False
    return any(fnmatch.fnmatch(path, g) or path.startswith(g.rstrip("/*") + "/") for g in watch)

def count(numstat):
    total = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-":
            continue
        if matches(parts[2]):
            total += int(parts[0]) + int(parts[1])
    return total

changed = count(git("diff", "--numstat", f"{state['lastSyncCommit']}..HEAD"))
changed += count(git("diff", "--numstat"))

turns = state.get("turnsSinceTrigger", cooldown) + 1
state["turnsSinceTrigger"] = turns

if changed >= threshold and turns > cooldown:
    state["turnsSinceTrigger"] = 0
    json.dump(state, open(state_path, "w"), indent=2)
    reason = (
        f"sys-sync checkpoint: {changed} lines have changed in watched areas since the last docs/report "
        f"sync point ({state['lastSyncCommit'][:10]}). Run the acumen plugin's sys-sync skill now: assess "
        "the changes conservatively, update the in-place reports and required documents ONLY if these "
        "changes genuinely alter what they state, and advance .ai/sys-sync-state.json either way. "
        "If you are mid-task, finish the current step first, then run sys-sync before ending the turn."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
else:
    json.dump(state, open(state_path, "w"), indent=2)
sys.exit(0)
PY
