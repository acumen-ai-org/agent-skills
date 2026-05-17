---
name: dev-release-candidate
description: Builds a release candidate for the current repository, driven by a dev-process.json config file. Creates the release candidate branch from origin/main, computes the main↔production scope, runs the configured analysis and review tools in parallel (delegating heavy or skill-kind tools to isolated sub-agents), optionally generates changelog/release notes and an aggregated report viewer, and makes the release-candidate commit. It does not freeze main, notify, or push — it can describe those steps when asked. Use when preparing or refreshing a release candidate.
---

# dev-release-candidate

A thin orchestrator. Every deterministic action is a script in the plugin's
`scripts/` directory; the Skill itself only fans analysis out to sub-agents
(B1) and invokes a configured generator/aggregator *skill* (B2/B3).

**This Skill performs:** create the release candidate branch + scope (A),
analysis/review (B1), changelog/notes (B2), aggregate reports (B3), the
release-candidate commit (B4).

**This Skill does not perform** the merge freeze, stakeholder notification, or
the push to origin. Those are real steps in the wider process — when the user
asks for the full process, describe them from
[Full process](#full-process-when-asked). Companion Skill:
`dev-release-publish`.

## Config

Behavior is read from `dev-process.json` at the consuming repo root. The
field-by-field contract is
[`references/dev-process-config.md`](references/dev-process-config.md).
`scripts/dev_process.py init` writes a documented default `dev-process.json`
if the file is absent; it never auto-commits. The JSON Schema ships bundled
with the plugin; `python3 scripts/dev_process.py schema` prints it on demand.

Ensure the consuming repo gitignores `reports.outputDir` (default
`.agents/release-reports`) so report artifacts never get swept into a stray
`git add -A`.

## Inputs

| Env | Default | Notes |
| --- | --- | --- |
| `CLAUDE_PLUGIN_ROOT` | plugin root | Locates `scripts/`. |
| `DEV_RELEASE_REPO` | `.` | The consuming repository to operate on. |
| `DEV_RELEASE_CONFIG` | `$DEV_RELEASE_REPO/dev-process.json` | Config path. |

`S="$CLAUDE_PLUGIN_ROOT/scripts"` below. All scripts share one exit-code
vocabulary (see [Exit codes](#exit-codes)).

## Procedure

```
- [ ] A.  Create release candidate branch → release_candidate_branch.sh + scope.sh
- [ ] B1. Analysis + review               → analysis_plan.py + (sub-agents | run_tool.sh) + analysis_gate.py
- [ ] B2. Changelog / notes               → configured generator, else skip
- [ ] B3. Aggregate reports               → configured aggregator, else skip
- [ ] B4. Release candidate commit        → release_candidate_commit.sh
```

### A. Create the release candidate branch

Bootstrap/validate config, branch from latest `origin/main`, compute scope:

```bash
python3 "$S/dev_process.py" check || python3 "$S/dev_process.py" init
bash "$S/release_candidate_branch.sh"
bash "$S/scope.sh"
```

If `init` wrote a new `dev-process.json`, tell the operator to review and
commit it before a real release. The release
candidate branch is, in practice, just `origin/main` at branch time.
`release_candidate_branch.sh` exit 2 → uncommitted tracked changes or missing
`origin/main`. `scope.sh` writes `scope.json`/`commits.txt`/`changed-files.txt`;
a `root` fallback warning means the whole history is in scope — confirm that is
intended.

### B1. Run analysis + review in parallel

Build the run plan, then fan out. **This is the one irreducible agent step.**

```bash
OUT="$DEV_RELEASE_REPO/$(python3 "$S/dev_process.py" emit | python3 -c 'import json,sys;print(json.load(sys.stdin)["reports"]["outputDir"])')"
python3 "$S/dev_process.py" emit | python3 "$S/analysis_plan.py" > "$OUT/_plan.jsonl"
```

Each line of `_plan.jsonl` is one entry:
`{id,kind,run,heavy,blocking,advisory,timeoutSeconds,report,...}`. Dispatch
**all entries concurrently in a single batch**:

- `kind:"command"` and not `heavy` → run directly:
  `bash "$S/run_tool.sh" <id> "<run>" "<reports.outputDir>" <report> <timeoutSeconds>`
  (it writes `OUT/<report>` and `OUT/<id>.exit`).
- `kind:"skill"` **or** `heavy:true` → delegate to an isolated agent (the
  Agent tool, `general-purpose`). The agent's task is the entry's `run` with
  `args` and the scope range from `scope.json`. Capture its output verbatim to
  `OUT/<report>`, and write the agent's success/failure as `0`/`1` to
  `OUT/<id>.exit`.

When every entry has an `OUT/<id>.exit`:

```bash
python3 "$S/analysis_gate.py" "$OUT/_plan.jsonl" "$OUT"
```

Exit 3 → a non-advisory blocking tool failed: stop, keep all report files,
surface `OUT/_summary.md`. Exit 0 → gate passed (an empty plan passes — a
zero-tool repo still produces a valid release candidate).

### B2. Generate changelog & release notes

Read `releaseNotes.generate`. If `run` is set:

- `kind:"command"` → `bash "$S/run_tool.sh" release-notes "<run>" "<reports.outputDir>" release-notes.md <timeout>`
- `kind:"skill"` → invoke that skill (isolated agent); write its output to
  `releaseNotes.path` / `releaseNotes.changelogPath`.

If `run` is null/empty: log `B2 skipped — no releaseNotes.generate configured`
and continue. A real no-op, not a failure.

### B3. Aggregate reports

Read `reports.aggregate`. Same rule as B2: run the configured command/skill if
set (it should read `reports.outputDir` and write `reports.viewerPath`);
otherwise log `B3 skipped — no reports.aggregate configured` and continue.

### B4. Create the release-candidate commit

```bash
bash "$S/release_candidate_commit.sh"
```

Commits the configured release notes / changelog. Report artifacts are **not**
committed here — `dev-release-publish` decides per `persistInRepo` what to keep
versus upload. "nothing to commit" is a clean exit 0.

## Full process (when asked)

The skills automate only part of the release. When the user asks for the whole
process, describe it; do **not** perform the external steps here.

| Step | Who |
| --- | --- |
| **A** create release candidate branch + scope | this Skill |
| **B0** freeze merges to `main` for the release window | external — your team's mechanism (a committed lock file + CI check, GitHub branch protection, or convention); exempt feedback PRs by an agreed label/branch |
| **B1–B3** analysis, review, changelog, aggregate | this Skill |
| **B4** release-candidate commit | this Skill |
| **D** notify stakeholders the candidate is ready | external — your team's channel/comms tooling |
| **E** collect feedback, then push the candidate to origin (force-push, overwriting the prior one) | external/manual — feedback lands as PRs to `main` exempt from the freeze; push the branch so `dev-release-publish` can verify it |
| **F** production release (tag + update production branch) | external — see `dev-release-publish` "Full process" |
| **G** merge production back to `main`, lift the freeze | external/manual |

## Outputs

- Local `release-candidate` branch with the release-candidate commit.
- `reports.outputDir/`: `scope.json`, `commits.txt`, `changed-files.txt`,
  per-tool reports, `_plan.jsonl`, `_gate.json`, `_summary.md`.

## Failure modes

- **Config invalid** → exit 2 with JSON-path errors; fix `dev-process.json`.
- **Blocking analysis failure** → gate exit 3; reports kept; fix the tool or
  mark the entry `advisory:true`.
- **Dirty tracked tree / no `origin/main`** → `release_candidate_branch.sh`
  exit 2.

## Exit codes

Shared across all `scripts/`: `0` ok · `1` usage · `2` precondition unmet ·
`3` blocking failure · `4` remote operation failed.
