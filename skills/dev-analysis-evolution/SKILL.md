---
name: dev-analysis-evolution
description: Analyzes how a repository changed across releases from git history alone — per-release-pair churn and files-changed-by-extension, code-maat temporal coupling and authorship, git-of-theseus code-survival cohorts, and a per-PR per-author activity classification (new vs updated feature, bug, technical, configuration, data; new vs existing patterns; optional repo-defined "vibe coder"). Emits two dev-report-fragment/v1 fragments (evolution, author-activity), both category evolution. Use when building a release report's evolution section, reviewing what changed and who changed it between two release tags, or assessing change concentration and code aging.
---

# dev-analysis-evolution

Pure-git evolution analysis. Two-stage like `content-to-image`'s
render→decode: collector/runner scripts write raw artifacts into one
`<out_dir>`; [`scripts/to-fragment.py`](scripts/to-fragment.py) (stdlib only)
normalizes them into two
[report fragments](../dev-report-framework/references/fragment-schema.md). The
scripts write only factual `metrics{}`/`body[]`; the
[`references/`](references/) roles add `summary` and narrative.

## Contents

- [Inputs](#inputs)
- [The two fragments at a glance](#the-two-fragments-at-a-glance)
- [Extension drill-down and module filter](#extension-drill-down-and-module-filter)
- [Procedure](#procedure)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

Every runner is one line; only I/O is positional.

| Input         | Used by | Notes |
| ------------- | ------- | ----- |
| `<repo>`      | all     | Path to a git working tree. |
| `<out_dir>`   | all     | One shared dir; every script reads/writes raw artifacts here. |
| `<ref_list>`  | `collect-history.sh` | Space/comma-separated release tags, oldest→newest, ≥ 2. |
| `<ref_range>` | `run-codemaat.sh`, `collect-author-activity.sh` | `<prev-release-tag>..main` form. |

`collect-history.sh` and `collect-author-activity.sh` are repo-level shared
scripts (`scripts/` at the repo root) so item 10 can reuse them. Requirements:
`bash`, `git`, `python3` (standard library only — no pip). `run-codemaat.sh`
needs Docker (image `adamtornhill/code-maat:1.0`, pinned). `run-git-of-theseus.sh`
needs `git-of-theseus-analyze` on `PATH` (`pip install git-of-theseus`; the
script never installs it). `az` (with the `azure-devops` extension,
authenticated) is optional — it enriches work-item types when present.

## The two fragments at a glance

Both `category: evolution`, written by `to-fragment.py`:

- **`evolution`** — `metrics{}` per-release-pair series (churn, coupling
  count, extensions touched); `body[]` an expandable
  extension→folder→file `table`, a per-release-pair churn `table`, a
  change-concentration `treemap`, and (optional) code-maat churn `table`.
- **`author-activity`** — `metrics{ pr_total, authors, new_feature_prs,
  updated_feature_prs, bug_prs, technical_prs, configuration_prs, data_prs,
  new_pattern_prs, existing_pattern_prs }` (plus `vibe_coders` **only** when a
  repo definition was found); a per-author summary `table`, a per-PR detail
  `table` with a filterable `module` column, and an author×PR-type `heatmap`.

Full contract:
[`references/fragment-schema.md` in dev-report-framework](../dev-report-framework/references/fragment-schema.md).

## Extension drill-down and module filter

**Evolution — three-level extension drill-down.** The "Files changed by
extension → folder → file" `table` uses recursive row `children`, collapsed by
default:

1. **Extension** (e.g. `ts`, `py`, `(none)`) with its total changed-file
   count across the whole ref range.
2. Expand → **folder**: the full folder path down to (but excluding) the
   file — e.g. `src/sub`, not just `sub` — each with its changed-file count.
3. Expand → **file**: individual file names under that folder with per-file
   change counts.

The framework's filter keeps a row when it or any descendant matches, so
typing a folder or file name narrows the tree; sort applies within each level.

**Author-activity — per-module filter.** The per-PR detail `table` carries a
`module` column. A module is the top-level path segment of a changed file, or
the git submodule path (from `.gitmodules`) when the file is under one — so
`vendor/lib/deep/x.c` reports module `vendor/lib`. A PR that spans modules is
emitted as **one detail row per module** (same PR/title/author repeated), so
the framework's built-in case-insensitive table filter narrows the table to a
single submodule / repository root by typing its name.

**Release vs delta view.** Release-over-release comparison sections carry
`view:"delta"` (per-release-pair churn, code-maat churn) and land in the right
**Δ vs previous** column; point-in-time inventories (the extension→folder→file
tree of this range, the change-concentration treemap) are default release view
and land left. Either fragment still emits and validates when only one view
has content (the author-activity fragment has no delta section).

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. History     — collect-history.sh <repo> <out> <ref_list>
- [ ] 2. code-maat    — run-codemaat.sh <repo> <out> <ref_range>   (Docker)
- [ ] 3. git-of-theseus — run-git-of-theseus.sh <repo> <out>        (pip tool)
- [ ] 4. Author bundle — collect-author-activity.sh <repo> <out> <ref_range>
- [ ] 5. Classify     — author-activity-classification.md role → out/author-activity.classified.json
- [ ] 6. Fragments    — to-fragment.py both <out>
- [ ] 7. Narrate      — evolution-narrative.md role enriches evolution.fragment.json
- [ ] 8. Validate     — validate_fragments.py <staging>  → must exit 0
```

Steps 2 and 3 are optional enrichers: if Docker / the pip tool is absent the
runner prints install instructions and exits `3`; skip it and continue —
`to-fragment.py` only requires `history.json` and `author-activity.json`.

### 1. History

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/collect-history.sh" <repo> <out_dir> "<ref_list>"
```

Writes `history.json` (per-adjacent-pair files-changed, lines, by-extension,
by-author, plus an `extension_tree` of extension→full-folder-path→file change
counts over the whole ref range) and the raw `--dirstat`/`--numstat` TSVs.
Exit `5` on a bad ref.

### 2. code-maat (optional)

```bash
bash "scripts/run-codemaat.sh" <repo> <out_dir> <ref_range>
```

Builds the `git2` log and runs churn + temporal-coupling + entity-ownership
via the pinned Docker image, writing `codemaat-*.csv`. Docker missing →
exit `3` with the `pip`/`docker run` lines; skip and continue.

### 3. git-of-theseus (optional)

```bash
bash "scripts/run-git-of-theseus.sh" <repo> <out_dir>
```

Detects `git-of-theseus-analyze` and emits `cohorts.json`/`survival.json`
(data, not the PNG — visualization is a `content-to-image` slot). Tool
missing → exit `3`; skip and continue.

### 4. Author bundle

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/collect-author-activity.sh" <repo> <out_dir> <ref_range>
```

Assembles the per-PR, per-author evidence bundle (`author-activity.json`); no
classification. A PR-unit is one squash commit on `main`; detection defaults
to `azure-squash` (set `PR_UNIT_STRATEGY=merge|trailer|squash-generic` to
override). Authors are canonicalized via `.mailmap`. Each PR-unit records
author, PR number, title, body, work-item ids (Azure work-item type resolved
via `az` when available), changed paths, the `modules[]` each PR touches
(top-level path segment, or `.gitmodules` submodule path when nested under
one), `--numstat`, and a static new-vs-existing pattern hint. It also locates
a repo-defined "vibe coder"
definition via
[`references/vibe-coder-definition-locations.md`](references/vibe-coder-definition-locations.md)
and copies its text in when found. Exit `5` on a bad ref.

### 5. Classify (role)

Run [`references/author-activity-classification.md`](references/author-activity-classification.md)
on `<out_dir>/author-activity.json`. Run it inline or delegate it to an
isolated agent (the Agent tool, `general-purpose`) passing the role file's
contents as the agent's instructions and the bundle as the task. Write the
role's JSON output verbatim to `<out_dir>/author-activity.classified.json`.
`to-fragment.py` reads it if present; without it the PR-type/pattern columns
stay empty (still contract-valid).

### 6. Fragments

```bash
python3 "scripts/to-fragment.py" both <out_dir>
```

Writes `<out_dir>/evolution.fragment.json` and
`<out_dir>/author-activity.fragment.json`. Use `evolution` or
`author-activity` as the first argument to emit only one.

### 7. Narrate (role)

Run [`references/evolution-narrative.md`](references/evolution-narrative.md) on
the merged evolution metrics; merge its `summary` + narrative `markdown`
section into `evolution.fragment.json`. Same inline-or-delegate choice as
step 5.

### 8. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <staging-dir>
```

Copy both `*.fragment.json` into one staging dir first. Exit `0` → hand to
`dev-report-build`. Exit `3` → fix and re-run; this is the feedback loop.

## Outputs

```
<out_dir>/
├── history.json + history-{dirstat,numstat}.tsv   (step 1)
├── codemaat-{churn,coupling,ownership}.csv          (step 2, optional)
├── cohorts.json / survival.json                     (step 3, optional)
├── author-activity.json                             (step 4)
├── author-activity.classified.json                  (step 5, role)
├── evolution.fragment.json                          (step 6 + 7)
└── author-activity.fragment.json                    (step 6 + 5)
```

The two `*.fragment.json` are the deliverables; the rest are diagnosable raw
inputs kept for re-runs.

## Failure modes

- **Bad / missing ref** → collector exits `5` with the offending ref on
  stderr; no fragment written. Fix the `ref_list`/`ref_range`.
- **Docker absent** → `run-codemaat.sh` exits `3` printing the install line
  and the exact pinned `docker run` line; no network attempted. Optional step,
  skip it.
- **`git-of-theseus-analyze` absent** → `run-git-of-theseus.sh` exits `3` with
  the `pip install` line; never auto-installs. Optional step, skip it.
- **Tool ran but no parseable output** → exit `2`, raw kept in `<out_dir>` for
  diagnosis, no fragment for that engine; `to-fragment.py` still proceeds from
  what is present.
- **No repo "vibe coder" definition** → not an error: the bundle's
  `vibe_coder_definition` is `null`, the `vibe_coders` metric is omitted, and
  the fragment surfaces "undetermined — no repository definition found". The
  label is never invented.
- **No classified bundle** → `to-fragment.py` still writes a contract-valid
  `author-activity` fragment with empty PR-type/pattern columns.

## Exit codes

Every runner (mirrors
[the standard table](../../docs/tools_implementation.md#standard-exit-codes-every-runner-mirror-in-its-skillmd)):

| Code | Meaning |
| ---- | ------- |
| `0`  | Raw written / fragment written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Tool ran but output unparseable; raw kept for diagnosis. |
| `3`  | Docker / pip tool missing; install + `docker run` lines printed. |
| `4`  | Tool ran and reported blocking findings; fragment written, `status: error`. |
| `5`  | Target or ref invalid (not a git repo, ref not found). |
