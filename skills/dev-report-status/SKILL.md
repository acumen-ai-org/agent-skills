---
name: dev-report-status
description: Runs last in a release report pipeline, after dev-report-overview and before/with dev-report-build. Reads the orchestrator's build-status.json (one row per report producer with its ok/failed/skipped outcome and exit code), rolls the outcomes into counts, and emits a single category:"report" fragment titled "Report build status" — metric cards plus a producer table — pinned second in the nav right after the overview. A synthesis role then appends an "Open questions & inferences — release or not?" section and an advisory decision checklist. Use as the report's own self-check: it tells the reader which parts of the report actually got produced.
---

# dev-report-status

Produces the report's self-check fragment: the one fragment that reports
whether every *other* producer ran. A stdlib script turns the orchestrator's
`build-status.json` into a contract-valid `category:"report"` fragment; a role
then appends the release-or-not judgment. The Skill is self-contained — no
external registered subagent. The script never calls an LLM (the judgment is a
role).

This Skill is **terminal in the fragment pipeline**: it runs *after*
`dev-report-overview` (which itself runs after every `dev-analysis-*` /
`dev-test-*` producer) and *before* (or alongside) `dev-report-build`. It
summarizes the run, so nothing it reports may still be pending.

## Contents

- [When to use](#when-to-use)
- [Inputs](#inputs)
- [Procedure](#procedure)
- [Where it sits in the pipeline](#where-it-sits-in-the-pipeline)
- [Outputs](#outputs)
- [Verify](#verify)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)
- [Out of scope](#out-of-scope)

## When to use

Use it as the final fragment-producing step of a release report run, after
`dev-report-overview` has staged its fragment. The orchestrator
(`dev-release-candidate`) writes `build-status.json` from the per-producer
exit codes it already captured; this Skill turns that into the report part
that tells a reader which producers actually ran.

## Inputs

| Input               | Required | Notes |
| ------------------- | -------- | ----- |
| `<build-status.json>` | yes    | The orchestrator's per-producer outcome roll-up (schema below). Lives in the work dir, **not** the staging fragments dir. |
| `<fragments-dir>`   | yes      | The same flat staging dir of `*.json` fragments `dev-report-build` consumes. The fragment is written into it. |

`build-status.json` schema:

```json
{
  "schema": "dev-report-build-status/v1",
  "release": "<release-id>",
  "generated_at": "<ISO-8601>",
  "producers": [
    { "skill": "dev-test-contracts", "fragment_id": "contracts",
      "status": "ok", "exit_code": 0, "message": "" }
  ]
}
```

`status` per producer is `ok` | `failed` | `skipped` (the orchestrator maps
exit `0`→`ok`, the documented tool/Docker-missing code→`skipped`, anything
else→`failed`). Requirements: `python3` (standard library only — no pip
packages). No Docker, no git, no network.

`S="scripts"` below.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. To-fragment — to-fragment.py → report-status fragment into <fragments-dir>
- [ ] 2. Synthesis   — report-status-synthesis role → release-or-not section + checklist
- [ ] 3. Validate    — validate_fragments.py <fragments-dir>  → must exit 0
```

### 1. To-fragment

```bash
python3 "$S/to-fragment.py" <build-status.json> <fragments-dir>
```

Reads `build-status.json`, rolls the producer outcomes into counts, and writes
`<fragments-dir>/report-status.fragment.json`: one `category:"report"`,
`id:"report-status"` fragment with metric cards and a producer table. The
fragment `status` is the worst producer outcome — `error` if any producer
failed, `warn` if any was skipped, else `ok`. The table carries that same
section `status`. This step is plain reading and counting; it does not call an
LLM. The fragment lands **in the fragments-dir** so `dev-report-build` pins it
second (right after the overview).

### 2. Synthesis (role)

Follow [`references/report-status-synthesis.md`](references/report-status-synthesis.md)
with the written fragment and `build-status.json` as input. Run it inline, or
— for fresh, unbiased context — delegate it to an isolated agent passing the
role file's contents as instructions and the fragment plus `build-status.json`
as the task. It returns two markdown sections (an "Open questions &
inferences — release or not?" section and an advisory decision checklist);
append each to the fragment's `body[]` as a
`{"type":"markdown","menu":"Release decision","status":"info"}` section. The
role never changes the counts, the producer rows, or the fragment `status`.

### 3. Validate (feedback loop)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <fragments-dir>
```

Exit `0` → the fragment (and every sibling) conforms; hand off to
`dev-report-build`. Exit `3` → per-file errors on stderr; fix the
`to-fragment.py` input (most often a malformed `build-status.json`) or the
appended sections and re-run. Do not build until this exits `0`.

## Where it sits in the pipeline

The status fragment summarizes whether the other producers ran, so its place
is fixed — last, after the overview:

```
dev-analysis-* / dev-test-*  →  stage fragments into <fragments-dir>
dev-report-overview          →  read them all, add overview.fragment.json
dev-report-status            →  read build-status.json, add report-status.fragment.json
dev-report-build             →  validate + assemble; overview pinned first, report second
```

The renderer pins a `category:"report"` fragment second in the left nav (right
after `overview`); this Skill pins nothing in code — that ordering is
renderer-owned.

## Outputs

- `<fragments-dir>/report-status.fragment.json` — one `category:"report"`,
  `id:"report-status"` fragment: metric cards + a producer table, with
  `summary`, `metrics{producers, ok, failed, skipped}`, the `❓` `help`
  string, and (after step 2) the release-or-not section and advisory
  checklist. The id is stable across releases so the split-screen diffs the
  producer counts release-over-release.

## Verify

- `report-status.fragment.json` exists in the fragments-dir;
  `validate_fragments.py <fragments-dir>` exits `0`.
- `category == "report"`, `id == "report-status"`, `status` is the worst
  producer outcome (`error` if any failed, else `warn` if any skipped, else
  `ok`).
- The producer table has one row per `build-status.json` producer; the metric
  cards match `metrics{producers, ok, failed, skipped}`.
- The fragment carries a non-empty `help` string.
- After step 2 the `body[]` ends with the two appended markdown sections.

## Failure modes

- **`build-status.json` unparseable / wrong schema / a bad producer status**
  → `to-fragment.py` exits `2`, nothing written; fix the orchestrator's
  `build-status.json` and re-run.
- **A producer is still pending** → `build-status.json` undercounts; this
  Skill ran too early. Re-run only after every producer (and the overview)
  has its outcome recorded.
- **Validation fails (exit 3)** → per-file errors on stderr; fix the
  `to-fragment.py` input or the appended sections and re-run steps 1–3.

## Exit codes

`to-fragment.py` mirrors the standard runner codes.

| Code | Meaning |
| ---- | ------- |
| `0`  | Report-status fragment written into the fragments-dir. |
| `1`  | Bad arguments (wrong positional count). |
| `2`  | `build-status.json` unreadable / unparseable / wrong schema; nothing written. |

Codes `3`–`5` are unused: this Skill installs no external tool and runs no
repository or VCS operation. `validate_fragments.py` carries its own exit
codes (see `dev-report-framework`'s `SKILL.md`).

## Out of scope

Building `build-status.json` or capturing producer exit codes (the
orchestrator does that before invoking this Skill). Re-running producers,
editing their fragments, or choosing the release id. The fragment shape and
the contract (`dev-report-framework`). The release-or-not narrative wording
(that is [`references/report-status-synthesis.md`](references/report-status-synthesis.md),
a role — not this script). Validating or building the report
(`dev-report-framework`).
