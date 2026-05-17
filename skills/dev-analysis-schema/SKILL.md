---
name: dev-analysis-schema
description: Diffs the API and schema surface of a repository between two git refs — OpenAPI (oasdiff, run separately over the public and private split), GraphQL SDL (graphql-inspector), and MCP tool/resource JSON-Schemas (a stdlib structural diff) — then emits one dev-report-fragment/v1 fragment in the schema category. status is error when any public breaking change exists, warn for private-only breaking or non-breaking change, ok with no diff. Use when assessing the contract impact of a release, reviewing breaking-change risk, or producing the API & contract surface slide of a release diff. No database schema diff.
---

# dev-analysis-schema

Produces one `schema` fragment for a release report: what changed across the
OpenAPI, GraphQL, and MCP contract surface between `ref_a` and `ref_b`, scored
by whether the break hits the **public** or only the **private** surface.

Two stages, mirroring the repo's runner contract: `diff-schemas.sh` runs the
engines and writes a merged `schema-diff.json` with `summary.hasDiff`;
`to-fragment.py` normalizes that into the fragment. The
[`references/schema-diff-summary.md`](references/schema-diff-summary.md) role
enriches the prose — **only when `hasDiff` is true**. Scripts never call an
LLM. The contract this targets is
[`dev-report-framework`](../dev-report-framework/references/fragment-schema.md).

## Contents

- [Inputs](#inputs)
- [What public vs private means](#what-public-vs-private-means)
- [Procedure](#procedure)
- [The fragment it emits](#the-fragment-it-emits)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

Positional, I/O only — the runner contract. No env vars are required;
visibility knobs are optional (see
[`references/visibility-rules.md`](references/visibility-rules.md)).

| Input       | Required | Notes |
| ----------- | -------- | ----- |
| `<repo>`    | yes      | Path to the git repository to analyze. |
| `<out_dir>` | yes      | Working dir for extracted schemas, per-engine raw diffs, the merged `schema-diff.json`, and the fragment. |
| `<ref_a>`   | yes      | The base ref (previous release tag/branch/SHA). |
| `<ref_b>`   | yes      | The revision ref (this release). |

Requirements: `bash`, `git`, `python3` (standard library only). `oasdiff` runs
via Docker; `graphql-inspector` runs via `npx` (Node). Either missing →
exit `3` with the exact install line and the pinned invocation; the script
never auto-installs. The MCP diff is pure stdlib and always available.

## What public vs private means

`classify-endpoints.py` splits each OpenAPI document into a public and a
private sub-document, and `run-oasdiff.sh` is run **twice** — once per
sub-document. A breaking change in the public sub-document is `status: error`;
a breaking change only in the private one is `status: warn`. The signals
(`x-internal`, path allowlist/denylist, security scheme; GraphQL `@internal`
/allowlist) and how to override them are in
[`references/visibility-rules.md`](references/visibility-rules.md). No database
schema is diffed — OpenAPI, GraphQL, and MCP only.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Diff      — diff-schemas.sh <repo> <out_dir> <ref_a> <ref_b>
- [ ] 2. Fragment  — to-fragment.py schema <out_dir>/schema-diff.json <out_dir>/schema-diff.fragment.json
- [ ] 3. Summarize — only if metrics.hasDiff == 1: run references/schema-diff-summary.md
- [ ] 4. Validate  — validate_fragments.py <staging>  → must exit 0
```

### 1. Diff

```bash
bash "scripts/diff-schemas.sh" <repo> <out_dir> <ref_a> <ref_b>
```

It extracts the OpenAPI/GraphQL/MCP schemas at both refs
(`extract-schemas.sh`), classifies endpoints (`classify-endpoints.py`), runs
`run-oasdiff.sh` over the public and the private split, runs
`run-graphql-inspector.sh`, runs `mcp-schema-diff.py`, and writes
`<out_dir>/schema-diff.json` with a `summary` block
(`hasDiff`, `publicBreaking`, `privateBreaking`, `totalChanges`). A trailing
`TOOL diff-schemas exit=0` line confirms. If an engine is missing the merged
diff records `toolMissing` and coverage is partial — re-run with it installed
for a complete result.

### 2. Fragment

```bash
python3 "scripts/to-fragment.py" schema \
  <out_dir>/schema-diff.json <out_dir>/schema-diff.fragment.json
```

Emits exactly one fragment, `id: schema-diff`, `category: schema`, with
`metrics.hasDiff`. Status is set factually: `error` (exit `4`) iff any public
breaking change, `warn` for private-only breaking or non-breaking change,
`ok` (exit `0`) with no diff. The trailing
`FRAGMENT schema-diff status=… hasDiff=… exit=…` line reports it.

### 3. Summarize (only if `metrics.hasDiff == 1`)

If — and only if — the fragment's `metrics.hasDiff` is `1`, run the
[`references/schema-diff-summary.md`](references/schema-diff-summary.md) role,
feeding it **only** `<out_dir>/schema-diff.json` and the emitted fragment
(never the full schemas). Replace the fragment's `summary` with the role's
`## summary` line and append its `## body-markdown` as a
`{ "type": "markdown", "title": "Assessment" }` section after the table. When
`hasDiff` is `0` skip this step entirely — the factual `ok` summary stands and
the role is not invoked.

### 4. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <staging-dir>
```

Put `schema-diff.fragment.json` in the staging dir handed to
`dev-report-build`. Exit `0` → conforms; exit `3` → fix and re-run. This is
the feedback loop; iterate before building.

## The fragment it emits

`category: schema`, `id: schema-diff` (stable across releases — the
cross-release diff key). `metrics`: `hasDiff`, `publicBreaking`,
`privateBreaking`, `totalChanges` (flat numbers, diffable). `body`: a
`metric-cards` summary, a filterable `table` of every change
(surface · visibility · criticality · location · detail), a tooling note if an
engine was missing, and — after the role runs — an `Assessment` markdown
section. Status mapping:

| Condition | `status` | Exit |
| --------- | -------- | ---- |
| No diff between refs | `ok` | `0` |
| Public breaking change present | `error` | `4` |
| Private-only breaking change | `warn` | `0` |
| Non-breaking change only | `warn` | `0` |

## Outputs

```
<out_dir>/
├── extract-manifest.json            # per-ref schema counts
├── ref_a/ ref_b/                    # extracted openapi/ graphql/ mcp/ per ref
├── classified/                      # public/private OpenAPI splits + classification
├── openapi-diff/  graphql-diff/  mcp-diff/   # per-engine raw diffs
├── schema-diff.json                 # merged diff + summary.hasDiff (stage-1 output)
└── schema-diff.fragment.json        # the dev-report-fragment/v1 fragment
```

`schema-diff.fragment.json` is the only file the framework consumes; the rest
are kept for diagnosis and re-runs.

## Failure modes

- **Not a git repo / ref not found** → `extract-schemas.sh` exits `5`; nothing
  diffed. Fix the path or ref and re-run.
- **Docker missing** → `run-oasdiff.sh` exits `3` with the Docker install line
  and the pinned `docker run`; `diff-schemas.sh` records `toolMissing` and
  continues with GraphQL+MCP. Install Docker for OpenAPI coverage.
- **Node/npx missing** → `run-graphql-inspector.sh` exits `3` with the Node
  install line and the pinned `npx`; GraphQL coverage is skipped, the rest
  proceeds.
- **An engine ran but emitted no parseable output** → that runner exits `2`,
  its raw output kept; the merged diff omits that surface.
- **No schemas found at either ref** → `hasDiff` is `0`, fragment `status: ok`,
  the summary role is not invoked (an honest "nothing to diff").
- **Public breaking change** → fragment `status: error`, `to-fragment.py`
  exits `4`; this is a successful analysis of a bad finding, not a tool break.

## Exit codes

`diff-schemas.sh` and the runners follow the standard table; `to-fragment.py`
carries the finding verdict:

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | An engine ran but its output was unparseable; raw kept. |
| `3`  | Docker or Node missing; install + pinned invocation printed. |
| `4`  | A public breaking change was found; fragment written, `status: error`. |
| `5`  | `<repo>` is not a git repo, or a ref does not exist. |
