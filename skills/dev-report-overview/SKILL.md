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
| `<work-dir>`      | yes      | Scratch dir for the rollup, the role trace, and the rendered PNG. Not the fragments-dir. |
| `<scope>`         | yes      | The ref-range / commit total being reported (e.g. `v2026.04.0..main`, `96`), passed to the role and recorded in `metrics`. |

Requirements: `python3` (standard library only — no pip packages).
`content-to-image` needs an image-generation backend (see its `SKILL.md`); a
non-2xx from that backend is a non-fatal degrade here (overview without an
image), not a pipeline stop. No Docker, no git.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Rollup     — read every staged fragment → <work-dir>/scope.json
- [ ] 2. Synthesis  — overview-synthesis role → bullets + image brief
- [ ] 3. Illustrate — invoke content-to-image with the brief → overview.png
- [ ] 4. To-fragment — to-fragment.py → overview fragment into <fragments-dir>
- [ ] 5. Validate   — validate_fragments.py <fragments-dir>  → must exit 0
```

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

### 3. Illustrate

Invoke the existing `content-to-image` Skill once with the image brief as
`$TEXT` (do **not** re-implement rendering here):

```bash
SLUG="overview" \
OUT_DIR="<work-dir>" \
TEXT="<image brief from step 2>" \
# then follow ${CLAUDE_PLUGIN_ROOT}/skills/content-to-image/SKILL.md
# (extract → art-direct → prompt-synth → render → decode)
```

The result is `<work-dir>/overview.png`. If `content-to-image` fails (image
API non-2xx), continue with the literal `NO-IMAGE` in step 4 — the overview
still ships with its bullets.

### 4. To-fragment

```bash
python3 "scripts/to-fragment.py" \
  <work-dir>/overview.bullets.md \
  <work-dir>/overview.png \
  <work-dir>/scope.json \
  <fragments-dir>/overview.fragment.json
```

Base64-encodes the PNG into a `data:image/png;base64,...` URI (standalone /
`file://` safe — the report needs no asset copy), and writes one
`category:"overview"`, `id:"overview"` fragment with an `image` body plus a
`markdown` bullets body, the role's `summary`, and the rollup `metrics`. Pass
the literal `NO-IMAGE` as the image arg to emit bullets only. The fragment
lands **in the fragments-dir** so `dev-report-build` pins it first.

### 5. Validate (feedback loop)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <fragments-dir>
```

Exit `0` → the overview (and every sibling) conforms; hand off to
`dev-report-build`. Exit `3` → per-file errors on stderr; fix the
`to-fragment.py` inputs and re-run. Do not build until this exits `0`.

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
- `<fragments-dir>/overview.fragment.json` — one `category:"overview"`,
  `id:"overview"` fragment: an `image` body (base64 data: URI) + a `markdown`
  bullets body, with `summary` and `metrics{fragments, ok, info, warn, error,
  commits, …}`. The id is stable across releases so the split-screen diffs the
  rollup counts release-over-release.

## Failure modes

- **A producer fragment is still pending** → the rollup undercounts; this Skill
  ran too early. Re-run only after every producer has staged its fragment.
- **`content-to-image` image API non-2xx** → not fatal here. Pass `NO-IMAGE`
  to `to-fragment.py`; the overview ships with bullets only, no `image` body.
- **`scope.json` unparseable / a metric non-numeric** → `to-fragment.py`
  exits `2`, inputs kept, no fragment written; fix the rollup and re-run.
- **Empty bullets file** → `to-fragment.py` exits `2`; re-run the synthesis
  role, then re-run `to-fragment.py`.
- **Validation fails (exit 3)** → per-file errors on stderr; fix the
  `to-fragment.py` inputs (most often a non-string `summary` or a non-number
  metric) and re-run step 4–5.

## Exit codes

`to-fragment.py` mirrors the standard runner codes.

| Code | Meaning |
| ---- | ------- |
| `0`  | Overview fragment written into the fragments-dir. |
| `1`  | Bad arguments (wrong positional count). |
| `2`  | An input was unreadable / unparseable, or a metric was non-numeric; inputs kept, no fragment written. |

Codes `3`–`5` are unused: this Skill installs no external tool and runs no
repository or VCS operation. `content-to-image` and
`validate_fragments.py` carry their own exit codes (see their `SKILL.md`).
