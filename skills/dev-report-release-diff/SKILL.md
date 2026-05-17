---
name: dev-report-release-diff
description: Builds a Slidev slide deck summarizing what changed between two git refs of a repository, one slide per applicable perspective. Reuses the repo-root diff collectors and the dev-analysis-schema diff chain for static facts, selects perspectives from a curated set (architecture impact, API & contract surface, data & schema changes, security & attack surface, dependency & supply-chain, test coverage & risk, performance & resource, operational & observability, plus a conditional mission-alignment slide), synthesizes a ≤120-word narrative per perspective, illustrates each with one content-to-image PNG, and assembles a deck with a closing risk summary. Use when producing a release-diff presentation, a stakeholder review deck, or the visual companion to a dev-report release report.
---

# dev-report-release-diff

Produces a Slidev deck for a release: one title slide, one slide per applicable
perspective (a `content-to-image` illustration + a ≤120-word narrative), and a
closing risk-summary slide. The static facts come from **reused** collectors —
this Skill never re-implements git diff parsing or schema diffing. Only the
per-perspective synthesis is a role. The Skill is self-contained — no external
registered subagent.

## Contents

- [Inputs](#inputs)
- [What it reuses, never duplicates](#what-it-reuses-never-duplicates)
- [Procedure](#procedure)
- [The perspectives](#the-perspectives)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

Positional for the scripts; the perspective set is derived, not configured.

| Input        | Required | Notes |
| ------------ | -------- | ----- |
| `<repo>`     | yes      | Path to the git repository to diff. |
| `<out_dir>`  | yes      | Working dir: collected facts, per-perspective trace, PNGs, `slides.md`, the built deck. |
| `<ref_range>`| yes      | `ref_a..ref_b` or `ref_a...ref_b`. Empty left side → first commit; empty right → `HEAD`. |
| `$KEEP_FILES`| no       | `false` (default) deletes the intermediate fact/trace files after the deck is built. `true` keeps them. |

Requirements: `bash`, `git`, `python3` (standard library only). `content-to-image`
needs an image-generation backend (see its `SKILL.md`). The deck build needs
**Node.js 18+** (`node` + `npx`); absent → `build-deck.sh` exits `3` with the
exact install URL and `npx` invocation — it never auto-installs and makes no
network call to detect.

## What it reuses, never duplicates

`collect-diff.sh` is an orchestrator over already-built assets. It locates them
by path relative to the repo root and **invokes them unchanged**:

- `scripts/collect-history.sh` (repo-root shared collector) — per-pair
  `git diff --dirstat`/`--numstat`, per-extension and per-author aggregation.
- `scripts/collect-author-activity.sh` (repo-root shared collector) — the
  per-PR-unit evidence bundle.
- `skills/dev-analysis-schema/scripts/diff-schemas.sh` — the OpenAPI/GraphQL/MCP
  schema-diff chain (it owns `extract-schemas.sh`, oasdiff, graphql-inspector,
  the MCP struct diff and writes `schema-diff.json`).

`collect-diff.sh` runs these three, then merges their JSON outputs into one
`diff-facts.json`. It contains no git-diff or schema-diff logic of its own — if
a reusable is missing it exits `2` rather than reimplementing it.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Collect diff facts  — collect-diff.sh <repo> <out_dir> <ref_range>
- [ ] 2. Schema diff          (done inside step 1: dev-analysis-schema chain)
- [ ] 3. Select perspectives  — references/perspective-discovery.md
- [ ] 4. Per perspective: synthesis (≤120-word narrative + image brief)
         then one content-to-image invocation → <slug>.png
- [ ] 5. Assemble slides.md   — references/deck-assembly.md
- [ ] 6. Build deck           — build-deck.sh <out_dir>/slides.md <out_dir>/deck
- [ ] 7. Cleanup (unless $KEEP_FILES=true)
```

### 1–2. Collect diff facts (static, includes the schema diff)

```bash
bash "scripts/collect-diff.sh" <repo> <out_dir> <ref_range>
```

Writes `<out_dir>/diff-facts.json` plus the reused collectors' raw output under
`history/`, `author-activity/`, `schema/`. The trailing
`TOOL collect-diff exit=<n>` line reports status; exit `5` means the repo or a
ref is invalid, `2` means a required reusable was not found.

### 3. Select perspectives

Run [`references/perspective-discovery.md`](references/perspective-discovery.md)
against `diff-facts.json` and any staged `dev-analysis-*` / `dev-test-*`
fragments. It admits a perspective **only when a static fact source produced
data** for it, from the curated set in
[`references/default-perspectives.md`](references/default-perspectives.md). The
mission-alignment slide is always present (absent docs → reflection-questions
slide).

### 4. Per perspective: synthesize, then illustrate

For each admitted perspective, run
[`references/perspective-synthesis.md`](references/perspective-synthesis.md)
with only that perspective's bound facts. It returns a ≤120-word narrative and
an `image-brief`. Unless the brief is the literal `NO-IMAGE` (mission
`status: info`), invoke `content-to-image` once with the brief as `$TEXT` and
the perspective's `$TYPE` hint:

```bash
TYPE="<hint from default-perspectives.md>" \
SLUG="perspective-<n>-<slug>" \
OUT_DIR="<out_dir>/visuals" \
TEXT="<image-brief from synthesis>" \
# then follow content-to-image/SKILL.md (extract → art-direct → prompt-synth → render → decode)
```

One `content-to-image` run per perspective. Capture the resulting
`<out_dir>/visuals/perspective-<n>-<slug>.png` path for assembly.

### 5. Assemble slides.md

Run [`references/deck-assembly.md`](references/deck-assembly.md) with each
perspective's narrative, PNG path (or `NO-IMAGE`), and fact-source `status`.
Write its verbatim output to `<out_dir>/slides.md`.

### 6. Build the deck

```bash
bash "scripts/build-deck.sh" <out_dir>/slides.md <out_dir>/deck
```

Runs Slidev via `npx`. Node/npx absent → exit `3` with the exact install line
and `npx` invocation; nothing is auto-installed.

### 7. Cleanup (default)

Unless `$KEEP_FILES=true`, remove the intermediate fact and per-perspective
trace files, keeping `slides.md`, `visuals/*.png`, and `deck/`:

```bash
[ "${KEEP_FILES:-false}" = "true" ] || rm -rf \
  "<out_dir>/history" "<out_dir>/author-activity" "<out_dir>/schema" \
  "<out_dir>/diff-facts.json"
```

Skip cleanup if any step failed — the intermediates are how the caller
diagnoses.

## The perspectives

The curated 8 plus the conditional mission slide, each bound to a
`dev-analysis-*` fact source and a `content-to-image` `$TYPE` hint, are defined
in [`references/default-perspectives.md`](references/default-perspectives.md). A
repo-specific perspective is admitted **only if a static fact source exists**
for it — the discovery rule in
[`references/perspective-discovery.md`](references/perspective-discovery.md). No
fact source → no slide; the mission slide is the sole always-present one.

## Outputs

```
<out_dir>/
├── diff-facts.json            # merged static facts (kept only with $KEEP_FILES=true)
├── history/ author-activity/ schema/   # reused collectors' raw output (same)
├── visuals/perspective-*.png  # one illustration per perspective
├── slides.md                  # the assembled Slidev deck source
└── deck/                      # the built Slidev deck (build-deck.sh)
```

The deck folder and `slides.md` are the deliverables. When run inside a
framework report the Skill may additionally emit a `mission`-adjacent summary
fragment per the [fragment contract](../dev-report-framework/references/fragment-schema.md);
standalone it emits the deck only.

## Failure modes

- **Not a git repo / ref not found** → `collect-diff.sh` exits `5`; nothing
  collected. Fix the path or `ref_range` and re-run.
- **A reused collector is missing** → `collect-diff.sh` exits `2` naming the
  missing path; it never reimplements the collector.
- **Schema engine (Docker/Node) missing** → the `dev-analysis-schema` chain
  records `toolMissing`; `diff-facts.json` carries `schema.tool_missing: true`
  and the API/contract perspective states the partial coverage rather than
  guessing.
- **Node/Slidev absent** → `build-deck.sh` exits `3` with the exact install URL
  and `npx` invocation; `slides.md` is still written, so the deck can be built
  later by hand.
- **`content-to-image` fails for a perspective** → that slide is assembled
  without its image (narrative only); the deck still builds.

## Exit codes

`collect-diff.sh` and `build-deck.sh` follow the standard table:

| Code | Meaning |
| ---- | ------- |
| `0`  | Step succeeded. |
| `1`  | Bad arguments (missing positional) / `slides.md` not found. |
| `2`  | `collect-diff.sh`: a required reusable not found. `build-deck.sh`: Slidev ran but failed. |
| `3`  | `build-deck.sh`: Node/npx missing; install URL + `npx` invocation printed. |
| `5`  | `<repo>` is not a git repo, or a ref in `<ref_range>` does not exist. |
