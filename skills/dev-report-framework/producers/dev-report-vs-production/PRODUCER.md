# dev-report-vs-production

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

Backfills the right **vs production** column for staged fragments whose
producer only emitted a left **This release** view. It augments existing
staged fragments in place — it never emits a new fragment and has no
`category` of its own. For each eligible fragment a role diffs the current
fragment against its same-id counterpart from the previous release; the
existing `content-to-image` one-shot script renders one infographic; a stdlib
script appends one `markdown` then one `image` section, both
`view:"production"`. The Skill is self-contained — no external registered
subagent. The script never calls an LLM and never generates an image (the
summary is a role; the image is `content-to-image`'s `text-to-image.sh`).

This Skill is **late in the fragment pipeline**: it runs *after* every
`dev-analysis-*` / `dev-test-*` producer has staged its fragment into the
fragments-dir and *before* `dev-report-overview` and `dev-report-build`. It
depends on the other fragments being staged, so nothing it augments may still
be pending; running before `dev-report-overview` lets the overview reflect the
augmented content.

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [How the prior fragment is located](#how-the-prior-fragment-is-located)
- [Where it sits in the pipeline](#where-it-sits-in-the-pipeline)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input             | Required | Notes |
| ----------------- | -------- | ----- |
| `<staging-dir>`   | yes      | The same flat staging dir of `*.json` fragments `dev-report-build` consumes. Fragments are read and, when eligible, augmented in place. |
| `<reports-root>`  | yes      | The reports root that holds `releases.json` (newest-first) and `<release>/data/<category>/<id>.json` for every prior release. At this point `releases.json` still reflects only prior releases — this release is not built yet. |
| `<work-dir>`      | yes      | Scratch dir for the per-fragment role output and the rendered image / data URI. Not the staging-dir. |

`content-to-image`'s one-shot script is located at
`${CLAUDE_PLUGIN_ROOT}/skills/content-to-image/scripts/text-to-image.sh`; the
shared validator at
`${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py`.
`backfill.py` is this Skill's own script, called by the relative path
`scripts/backfill.py`.

Requirements: `python3` (standard library only — no pip packages) and `bash`.
`text-to-image.sh` guarantees an image artifact even with no image backend (it
writes a diagnostic SVG and still exits `0`), so a missing image backend is a
visible degrade, never a pipeline stop.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Plan       — backfill.py plan <staging-dir> <reports-root>
- [ ] 2. Per fragment listed by plan:
- [ ]    a. Synthesis  — vs-production-synthesis role → summary + image brief
- [ ]    b. Illustrate  — text-to-image.sh <brief> → image; base64 → data: URI
- [ ]    c. Append      — backfill.py apply <fragment> <summary> <datauri>
- [ ] 3. Validate   — validate_fragments.py <staging-dir>  → must exit 0
```

If step 1 prints no lines (no prior report / no prior counterpart for any
fragment / every fragment already has a production view), this Skill is a
**no-op**: nothing is changed, the vs-production column stays empty, and you
hand off directly to `dev-report-overview` / `dev-report-build`. This is the
expected first-release behavior.

### 1. Plan

```bash
python3 "scripts/backfill.py" plan <staging-dir> <reports-root>
```

Each output line is `<fragment-path>\t<prev-fragment-path>` — one per staged
fragment that has **zero** `view:"production"` sections **and** has a prior
same-id fragment. Fragments that already carry a production view, and
fragments new this release (no prior counterpart), are not listed and are left
unchanged. Exit `0` with no lines is the documented no-op; stop here.

### 2. Per fragment

For every line from step 1, with `<fragment>` and `<prev>` the two paths:

#### 2a. Synthesis (role)

Follow [`references/vs-production-synthesis.md`](references/vs-production-synthesis.md)
with the **current** fragment JSON (`<fragment>`) and the **previous** same-id
fragment JSON (`<prev>`) as input. Run it inline, or — for fresh, unbiased
context — delegate it to an isolated agent passing the role file's contents as
instructions and the two fragment JSONs as the task. Capture its output
verbatim. Write the `## Summary` block to
`<work-dir>/<id>.vs-production.md`; keep the `## Image brief` line for 2b.

#### 2b. Illustrate

Invoke the existing `content-to-image` one-shot script once with the image
brief — do **not** re-implement rendering here:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/content-to-image/scripts/text-to-image.sh" \
  "<image brief from 2a>" "<work-dir>/<id>.vs-production.png"
```

It always writes an image and exits `0` whenever any image was written — a
real PNG on success, or a diagnostic fallback SVG with per-attempt provider /
HTTP status if generation failed. Base64-encode the written file into a
`data:` URI (PNG → `data:image/png;base64,…`; the fallback SVG →
`data:image/svg+xml;base64,…`) and write that single line to
`<work-dir>/<id>.vs-production.datauri`.

#### 2c. Append

```bash
python3 "scripts/backfill.py" apply \
  <fragment> \
  <work-dir>/<id>.vs-production.md \
  <work-dir>/<id>.vs-production.datauri
```

Appends to that fragment's `body[]`, in order, a
`{ "type":"markdown", "view":"production", "title":"vs production", "md": … }`
section then a `{ "type":"image", "view":"production", "src": <data-uri>,
"alt":"vs production summary" }` section, and rewrites the fragment. Existing
sections are not touched; no `menu` is added (these are view-scoped and fill
the right column).

### 3. Validate (feedback loop)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <staging-dir>
```

Exit `0` → every augmented fragment (and every sibling) still conforms; hand
off to `dev-report-overview` / `dev-report-build`. Exit `3` → per-file errors
on stderr; fix the offending `apply` input (most often a non-string summary or
an empty data URI) and re-run that fragment's 2c–3. `backfill.py` does not
validate; this shared validator is the acceptance gate and must exit `0`
before any build.

## How the prior fragment is located

The previous release is `releases.json[0]` read from `<reports-root>` — at
this point `releases.json` still lists only prior releases because this release
is not built yet, so `releases[0]` is the production baseline. For a staged
fragment with `id` `X` and `category` `C`, its prior counterpart is
`<reports-root>/<releases[0].path or releases[0].id>/data/C/X.json`.
`dev-report-build` always writes `data/<category>/<id>.json` for every
fragment (even when embedded), so the prior file exists whenever that report
part shipped last release. A stable `id` across releases is the join key — the
same key the split-screen diff uses. No reports-root, no `releases.json`, no
prior release, or no prior file with the same `id` ⇒ that fragment is skipped.

## Where it sits in the pipeline

```
dev-analysis-* / dev-test-*  →  stage fragments into <staging-dir>
dev-report-vs-production     →  backfill view:"production" sections in place
dev-report-overview          →  read them all, add overview.fragment.json
dev-report-build             →  validate + assemble
```

Run it after every producer and before `dev-report-overview`, so the overview
rolls up the augmented set, and before the final build. It changes no
fragment's `id`, `category`, `status`, or `metrics{}` and emits no fragment —
it only appends two right-column sections to fragments that lacked them.

## Outputs

- `<work-dir>/<id>.vs-production.md` — the role's change summary. Intermediate,
  not a fragment — keep it out of the validated `<staging-dir>`.
- `<work-dir>/<id>.vs-production.png` — the `content-to-image` infographic
  (a real PNG, or the guaranteed fallback SVG). Intermediate; embedded as a
  data: URI, so the report does not reference this file.
- `<work-dir>/<id>.vs-production.datauri` — the base64 `data:` URI. Intermediate.
- `<staging-dir>/<…>.json` (augmented in place) — each eligible fragment gains
  one `markdown` then one `image` section, both `view:"production"`,
  `title:"vs production"`. Its `id`, `category`, `status`, `metrics{}`, and
  existing sections are unchanged, so the cross-release diff and the left
  column are identical to before.

## Failure modes

- **No prior report** (no reports-root / no `releases.json` / no prior release)
  → `plan` prints nothing, exits `0`; the Skill is a no-op and the
  vs-production column stays empty (first-release behavior).
- **Prior fragment absent** (new fragment this release, or that report part
  did not ship last release) → `plan` skips that fragment; it is left
  unchanged.
- **Fragment already has a `view:"production"` section** → `plan` skips it;
  its existing right column is preserved untouched.
- **Image generation failed** → `text-to-image.sh` still writes its diagnostic
  fallback SVG and exits `0`; that SVG is embedded as the `image` section so
  the vs-production view still ships, with the failure visible in the image.
- **A staged fragment is unreadable / not JSON** → `backfill.py` exits `2`,
  nothing written; fix the upstream producer and re-run.
- **`staging-dir` not a directory** → `backfill.py plan` exits `5`.
- **Validation fails (exit 3)** → per-file errors on stderr from
  `validate_fragments.py`; fix the offending `apply` input and re-run that
  fragment's 2c then step 3. Do not build until this exits `0`.

## Exit codes

`backfill.py` mirrors the standard runner codes.

| Code | Meaning |
| ---- | ------- |
| `0`  | `plan` succeeded (zero or more lines printed); or `apply` rewrote the fragment. |
| `1`  | Bad arguments (unknown subcommand or wrong positional count). |
| `2`  | An input fragment / summary / data-URI file was unreadable or not valid JSON; nothing written. |
| `5`  | `staging-dir` (or, for `plan`, the reports-root path given) is not a usable directory. |

Codes `3`–`4` are unused here: this Skill installs no external tool and runs
no VCS operation. `text-to-image.sh` and `validate_fragments.py` carry their
own exit codes (see their `SKILL.md`); `validate_fragments.py` exit `3` is the
acceptance-gate failure.
