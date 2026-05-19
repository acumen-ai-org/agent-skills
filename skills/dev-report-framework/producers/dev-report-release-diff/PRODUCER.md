# dev-report-release-diff

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

Produces one `report`-category fragment for a release: a multi-perspective
`git diff` summary, one section group per applicable perspective (a
`content-to-image` illustration + a ≤120-word narrative), then a closing
risk-summary section. The static facts come from **reused** collectors — this
producer never re-implements git diff parsing or schema diffing. Only the
per-perspective synthesis is a role; the fragment assembly is deterministic
(`scripts/to-fragment.py`).

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
| `<out_dir>`  | yes      | Working dir: collected facts, per-perspective trace, PNGs. |
| `<ref_range>`| yes      | `ref_a..ref_b` or `ref_a...ref_b`. Empty left side → first commit; empty right → `HEAD`. |
| `<staging>`  | yes      | The report staging fragments dir — where the `release-diff` fragment is written. |

Requirements: `bash`, `git`, `python3` (standard library only).
`content-to-image` needs an image-generation backend (see its `SKILL.md`).
There is no Node/Slidev dependency — the deliverable is a report fragment, not
a deck.

## What it reuses, never duplicates

`collect-diff.sh` is an orchestrator over already-built assets. It locates them
by path and **invokes them unchanged**:

- `${CLAUDE_PLUGIN_ROOT}/scripts/collect-history.sh` (repo-root shared
  collector) — per-pair `git diff --dirstat`/`--numstat`, per-extension and
  per-author aggregation.
- `${CLAUDE_PLUGIN_ROOT}/scripts/collect-author-activity.sh` (repo-root shared
  collector) — the per-PR-unit evidence bundle.
- `${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/producers/dev-analysis-schema/scripts/diff-schemas.sh`
  — the OpenAPI/GraphQL/MCP schema-diff chain (owns `extract-schemas.sh`,
  oasdiff, graphql-inspector, the MCP struct diff; writes `schema-diff.json`).

`collect-diff.sh` runs these three, then merges their JSON into one
`diff-facts.json`. It contains no git-diff or schema-diff logic of its own — a
missing reusable is exit `2`, never reimplemented.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Collect diff facts   — collect-diff.sh <repo> <out_dir> <ref_range>
- [ ] 2. Schema diff           (done inside step 1: dev-analysis-schema chain)
- [ ] 3. Select perspectives   — references/perspective-discovery.md
- [ ] 4. Per perspective: synthesis (≤120-word narrative + image brief),
         then one content-to-image invocation → <slug>.png (unless NO-IMAGE)
- [ ] 5. Assemble perspectives.json (slug, name, status, narrative, image)
- [ ] 6. Build fragment        — to-fragment.py diff-facts.json perspectives.json <staging>
- [ ] 7. Validate              — validate_fragments.py <staging>  → must exit 0
```

### 1–2. Collect diff facts (static, includes the schema diff)

```bash
bash "scripts/collect-diff.sh" <repo> <out_dir> <ref_range>
```

Writes `<out_dir>/diff-facts.json` plus the reused collectors' raw output under
`history/`, `author-activity/`, `schema/`. Exit `5` means the repo or a ref is
invalid; `2` means a required reusable was not found.

### 3. Select perspectives

Run [`references/perspective-discovery.md`](references/perspective-discovery.md)
against `diff-facts.json` and any staged `dev-analysis-*` / `dev-test-*`
fragments. It admits a perspective **only when a static fact source produced
data** for it, from the curated set in
[`references/default-perspectives.md`](references/default-perspectives.md). The
mission-alignment perspective is always present (absent docs → its narrative is
the reflection questions, no image).

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

One `content-to-image` run per perspective; capture
`<out_dir>/visuals/perspective-<n>-<slug>.png`.

### 5. Assemble perspectives.json

Write `<out_dir>/perspectives.json` — the deterministic hand-off to the
assembler. One entry per admitted perspective, in discovery order:

```json
{ "perspectives": [
  { "slug": "<slug>", "name": "<Perspective name>",
    "status": "ok|info|warn|error",
    "narrative": "<≤120-word prose from synthesis>",
    "image": "<png path, or null for a NO-IMAGE perspective>" }
] }
```

`status` is the perspective's bound fact-source status. `image` is `null` only
for a mission `status: info` perspective (narrative = the reflection questions).

### 6. Build the fragment

```bash
python3 "scripts/to-fragment.py" <out_dir>/diff-facts.json <out_dir>/perspectives.json <staging>
```

Writes `<staging>/release-diff.fragment.json` — `category:"report"`, one menu
group per perspective (image section + narrative markdown), then a
`Release risk summary` section whose roll-up is the worst perspective status.
Every section is left-column (untagged `view`). Assembly is deterministic; the
script never calls an LLM.

### 7. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <staging>
```

Exit `0` → conformant, hand off to the build. Exit `3` → fix and re-run.

## The perspectives

The curated 8 plus the conditional mission perspective, each bound to a
`dev-analysis-*` fact source and a `content-to-image` `$TYPE` hint, are defined
in [`references/default-perspectives.md`](references/default-perspectives.md). A
repo-specific perspective is admitted **only if a static fact source exists**
for it — the discovery rule in
[`references/perspective-discovery.md`](references/perspective-discovery.md). No
fact source → no section group; the mission perspective is the sole
always-present one. The fragment contract is
[`../../references/fragment-schema.md`](../../references/fragment-schema.md).

## Outputs

```
<out_dir>/
├── diff-facts.json            # merged static facts
├── history/ author-activity/ schema/   # reused collectors' raw output
├── visuals/perspective-*.png  # one illustration per perspective
└── perspectives.json          # the deterministic assembler hand-off
<staging>/
└── release-diff.fragment.json # the deliverable (dev-report-fragment/v1)
```

The fragment is the deliverable; the framework lays it out under the **Report**
nav area like any other `report`-category fragment.

## Failure modes

- **Not a git repo / ref not found** → `collect-diff.sh` exits `5`; nothing
  collected. Fix the path or `ref_range` and re-run.
- **A reused collector is missing** → `collect-diff.sh` exits `2` naming the
  missing path; it never reimplements the collector.
- **Schema engine (Docker/Node) missing** → the `dev-analysis-schema` chain
  records `toolMissing`; `diff-facts.json` carries `schema.tool_missing: true`
  and the API/contract perspective states the partial coverage rather than
  guessing.
- **`content-to-image` fails for a perspective** → set that entry's `image` to
  `null`; the perspective is still emitted (narrative only) and the fragment
  still validates.

## Exit codes

`collect-diff.sh` and `to-fragment.py` follow the standard table:

| Code | Meaning |
| ---- | ------- |
| `0`  | Step succeeded. |
| `1`  | Bad arguments (missing positional). |
| `2`  | `collect-diff.sh`: a required reusable not found. `to-fragment.py`: an input unreadable / malformed (nothing written). |
| `5`  | `<repo>` is not a git repo, or a ref in `<ref_range>` does not exist. |
