---
name: dev-report-overview
description: Runs last in a release report pipeline, after every dev-analysis-/dev-test- producer has staged its fragment and before dev-report-build. Reads the same staging dir the build consumes, rolls up counts by status and per-category highlights and total scope, runs the overview-synthesis role to produce high-level scope bullets plus a one-line image brief, invokes the content-to-image Skill to render an infographic PNG, then emits a single category:"overview" fragment (a base64 data: URI image body plus a markdown bullets body) into the staging dir so the build pins it first as the report's landing page. Use as the final fragment-producing step before assembling a release report.
---

# dev-report-overview

Produces the report's landing fragment: the one fragment that reads all the
others. A role digests the staged set into scope bullets and an image brief;
the existing `content-to-image` Skill renders the infographic; a stdlib script
wraps both into a contract-valid `category:"overview"` fragment. The Skill is
self-contained — no external registered subagent. The script never calls an
LLM (the bullets are a role; the image is `content-to-image`).

This Skill is **terminal in the fragment pipeline**: it runs *after* every
`dev-analysis-*` / `dev-test-*` producer has staged its fragment into the
fragments-dir and *before* (or at the start of) `dev-report-build`. It depends
on the other fragments, so nothing it summarizes may still be pending.

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [Where it sits in the pipeline](#where-it-sits-in-the-pipeline)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input             | Required | Notes |
| ----------------- | -------- | ----- |
| `<fragments-dir>` | yes      | The same flat staging dir of `*.json` fragments `dev-report-build` consumes. Read for the rollup; the overview fragment is written back into it. |
| `<work-dir>`      | yes      | Scratch dir for the rollup, the role trace, the rendered PNGs, `changes_shifts.json`, and `overview-extras.json`. Holds `commits.txt` + `changed-files.txt` from `scope.sh`, and `author-activity.classified.json` when `dev-analysis-evolution` ran. Not the fragments-dir. |
| `<scope>`         | yes      | The ref-range / commit total being reported (e.g. `v2026.04.0..main`, `96`), passed to the role and recorded in `metrics`. |
| `<repo>`          | optional | The repo root carrying `dev-process.json`; lets `classify-changes.py` fold shift files to module ids. Absent ⇒ shifts fold to `root`. |

Requirements: `python3` (standard library only — no pip packages).
`content-to-image` needs an image-generation backend (see its `SKILL.md`); a
non-2xx from that backend is a non-fatal degrade here (overview without an
image), not a pipeline stop. No Docker, no git.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Rollup     — read every staged fragment → <work-dir>/scope.json
- [ ] 2. Synthesis  — overview-synthesis role → bullets + image brief
- [ ] 3. Classify   — classify-changes.py → <work-dir>/changes_shifts.json
- [ ] 4. Narrate    — diff-view + change-shift-narrative roles → overview-extras.json
- [ ] 5. Illustrate — content-to-image: top infographic + per-sub-section heroes
- [ ] 6. To-fragment — to-fragment.py (+ overview-extras.json) → <fragments-dir>
- [ ] 7. Validate   — validate_fragments.py <fragments-dir>  → must exit 0
```

Steps 3–5 are the extended Overview summary; they are OPTIONAL. Skip 3–5 and
omit the 5th `to-fragment.py` argument and the run is byte-identical to the
infographic-plus-bullets Overview. The end-to-end order with the extras is:
the producers stage their fragments → classify the work-dir → run the
narrative roles → render the heroes → call `to-fragment.py` with the merged
extras.

### 1. Rollup

Read every `*.json` in `<fragments-dir>` (skip non-fragments). Build
`<work-dir>/scope.json`:

```json
{
  "title": "Release overview",
  "status": "warn",
  "summary": "",
  "image_alt": "Release overview infographic",
  "metrics": { "fragments": 7, "ok": 3, "info": 1, "warn": 2,
               "error": 1, "commits": 96 }
}
```

`metrics{}` is a flat `string → number` map (the contract's diff surface):
fragment count, one count per `status`, the commit/scope total, and any other
roll-up number worth diffing release-over-release. `status` is the worst status
present (`error` > `warn` > `info` > `ok`). Leave `summary` empty — the role
sets it. This step is plain reading and counting; do not call an LLM for it.

### 2. Synthesis (role)

Follow [`references/overview-synthesis.md`](references/overview-synthesis.md)
with the staged fragment set and `scope.json` as input. Run it inline, or — for
fresh, unbiased context — delegate it to an isolated agent passing the role
file's contents as instructions and the fragment summaries + rollup as the
task. Capture its output verbatim. Apply its `## Summary` line to
`scope.json`'s `summary`; write the `## Scope bullets` block to
`<work-dir>/overview.bullets.md`; keep the `## Image brief` line for step 3.

### 3. Classify (deterministic, optional)

Run the deterministic classifier over the work-dir to group the release's
commits by change type and detect architectural-shift signals. It calls no
model:

```bash
python3 "scripts/classify-changes.py" \
  --commits  <work-dir>/commits.txt \
  --changed  <work-dir>/changed-files.txt \
  --classified <work-dir>/author-activity.classified.json \
  --config   <repo>/dev-process.json \
  --repo     <repo> \
  --out      <work-dir>/changes_shifts.json
```

`commits.txt` and `changed-files.txt` are written by `scope.sh`;
`author-activity.classified.json` exists only when `dev-analysis-evolution`
ran (drop `--classified` otherwise). `--config`/`--repo` fold each shift's
files to module ids via the shared `scripts/modules.py`. Empty inputs ⇒ empty
groups/rows, exit 0 — no fabricated content. Skip this step (and 4–5) for the
plain Overview.

### 4. Narrate (roles, optional)

Run two role steps and merge their output into `<work-dir>/overview-extras.json`:

- [`references/diff-view.md`](references/diff-view.md) — the before/after
  perspectives. Drop the `workflow` perspective unless the orchestrator passes
  an OPTIONAL `reports.workflowDocsGlob` from `dev-process.json`.
- [`references/change-shift-narrative.md`](references/change-shift-narrative.md)
  — ≤ 5 bullets per change group, then write `overview-extras.json` by merging
  `changes_shifts.json` **verbatim** (counts, signals, module ids are the
  script's — never re-derived) with the prose bullets and the diff-view
  perspectives.

### 5. Illustrate

Invoke the existing `content-to-image` Skill (do **not** re-implement
rendering here) for the top infographic with the step-2 image brief as
`$TEXT`:

```bash
SLUG="overview" \
OUT_DIR="<work-dir>" \
TEXT="<image brief from step 2>" \
# then follow ${CLAUDE_PLUGIN_ROOT}/skills/content-to-image/SKILL.md
```

The result is `<work-dir>/overview.png`. When the extended summary is on, also
render one hero per sub-section following
[`references/hero-briefs.md`](references/hero-briefs.md): invoke
`${CLAUDE_PLUGIN_ROOT}/skills/content-to-image/scripts/text-to-image.sh
<brief> <work-dir>/<slug>.png` for each of `overview-summary`,
`overview-diff`, `overview-changes`, `overview-shifts`, then record each path
into `overview-extras.json.images` under `summary` / `diff-view` / `changes` /
`shifts`. Honor the `DEV_REPORT_NO_IMAGES=1`-style opt-out — every hero falls
back to content-to-image's guaranteed tile and never blocks. If
`content-to-image` fails (image API non-2xx), continue with the literal
`NO-IMAGE` for the top infographic — the overview still ships with its
bullets.

### 6. To-fragment

```bash
python3 "scripts/to-fragment.py" \
  <work-dir>/overview.bullets.md \
  <work-dir>/overview.png \
  <work-dir>/scope.json \
  <fragments-dir>/overview.fragment.json \
  <work-dir>/overview-extras.json
```

Base64-encodes the PNG into a `data:image/png;base64,...` URI (standalone /
`file://` safe — the report needs no asset copy), and writes one
`category:"overview"`, `id:"overview"` fragment with an `image` body plus a
`markdown` bullets body, the role's `summary`, and the rollup `metrics`. Pass
the literal `NO-IMAGE` as the image arg to emit bullets only. The optional 5th
argument adds the `Diff view` / `Changes` / `Shifts` sub-sections and their
heroes; **omit it** for a fragment byte-identical to the plain Overview. Every
appended section is untagged ⇒ the "This release" column; never
`view:"production"`. The fragment lands **in the fragments-dir** so
`dev-report-build` pins it first.

### 7. Validate (feedback loop)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <fragments-dir>
```

Exit `0` → the overview (and every sibling) conforms; hand off to
`dev-report-build`. Exit `3` → per-file errors on stderr; fix the
`to-fragment.py` inputs and re-run. Do not build until this exits `0`.

When the extras were passed, also assert the Overview menu is
`Summary · Diff view · Changes · Shifts` — the distinct `section.menu` labels
in the written fragment must be exactly that set (heroes inherit the menu of
the sub-section they head; none adds its own). A run without the extras has no
`menu` labels and is byte-identical to the plain Overview.

## Where it sits in the pipeline

The overview is the only fragment that summarizes the others, so its place is
fixed:

```
dev-analysis-* / dev-test-*  →  stage fragments into <fragments-dir>
dev-report-overview          →  read them all, add overview.fragment.json
dev-report-build             →  validate + assemble, overview pinned first
```

Run it after every producer and before the final build. A
`category:"overview"` fragment is pinned first in the left nav and is the
default page on load (lexically-first `id` if several — `overview` sorts
early); it otherwise renders like any fragment.

## Outputs

- `<work-dir>/scope.json` — the factual rollup (counts, scope). Intermediate,
  not a fragment — keep it out of the validated `<fragments-dir>`.
- `<work-dir>/overview.bullets.md` — the role's scope bullets. Intermediate.
- `<work-dir>/overview.png` — the `content-to-image` infographic (absent if
  the image backend failed). Intermediate; it is embedded as a data: URI, so
  the report does not reference this file.
- `<work-dir>/changes_shifts.json` — the deterministic classifier output
  (`changes.groups[]`, `shifts.rows[]`). Intermediate, only when steps 3–5
  ran.
- `<work-dir>/overview-extras.json` — the merged `diff_view` / `changes` /
  `shifts` / `images`. Intermediate; passed as `to-fragment.py`'s 5th
  argument. Only when steps 3–5 ran.
- `<work-dir>/overview-{summary,diff,changes,shifts}.png` — the per-sub-section
  heroes (the fallback tile when the backend failed or images are opted out).
  Intermediate; embedded as data: URIs.
- `<fragments-dir>/overview.fragment.json` — one `category:"overview"`,
  `id:"overview"` fragment: an `image` body (base64 data: URI) + a `markdown`
  bullets body, with `summary` and `metrics{fragments, ok, info, warn, error,
  commits, …}`. With the extras it also carries the `Diff view`, `Changes`,
  and `Shifts` sub-sections (each untagged ⇒ "This release" column) and their
  heroes; without the extras it is byte-identical to the plain Overview. The
  id is stable across releases so the split-screen diffs the rollup counts
  release-over-release.

## Failure modes

- **A producer fragment is still pending** → the rollup undercounts; this Skill
  ran too early. Re-run only after every producer has staged its fragment.
- **`content-to-image` image API non-2xx** → not fatal here. Pass `NO-IMAGE`
  to `to-fragment.py`; the overview ships with bullets only, no `image` body.
- **`scope.json` unparseable / a metric non-numeric** → `to-fragment.py`
  exits `2`, inputs kept, no fragment written; fix the rollup and re-run.
- **Empty bullets file** → `to-fragment.py` exits `2`; re-run the synthesis
  role, then re-run `to-fragment.py`.
- **`commits.txt` / `changed-files.txt` absent or empty** →
  `classify-changes.py` emits empty `groups`/`rows`, exit 0 — the Overview
  ships without the extended summary, nothing is fabricated.
- **Malformed `overview-extras.json`** (e.g. a diff-view item with both
  `before` and `after` empty) → `to-fragment.py` exits `2`, no fragment
  written; fix the narrative role's output and re-run step 6.
- **Validation fails (exit 3)** → per-file errors on stderr; fix the
  `to-fragment.py` inputs (most often a non-string `summary` or a non-number
  metric) and re-run step 6–7.

## Exit codes

`to-fragment.py` and `classify-changes.py` mirror the standard runner codes.

| Code | `to-fragment.py` | `classify-changes.py` |
| ---- | ---------------- | --------------------- |
| `0`  | Overview fragment written into the fragments-dir. | `changes_shifts.json` written (possibly empty). |
| `1`  | Bad arguments (wrong positional count). | Bad arguments. |
| `2`  | An input was unreadable / unparseable, a metric was non-numeric, or the extras were malformed; inputs kept, nothing written. | `commits.txt` / `changed-files.txt` / `--classified` unreadable. |

Codes `3`–`5` are unused: this Skill installs no external tool and runs no
repository or VCS operation. `content-to-image` and
`validate_fragments.py` carry their own exit codes (see their `SKILL.md`).
