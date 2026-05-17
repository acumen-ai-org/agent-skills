# Report-fragment contract (dev-report-fragment/v1)

The single source of truth for the JSON a producer Skill emits. This file
ships inside the Skill so the contract travels with the renderer.
`validate_fragments.py` enforces exactly what is written here.

## Contents

- [Top-level fields](#top-level-fields)
- [metrics is a flat number map](#metrics-is-a-flat-number-map)
- [Body section types](#body-section-types)
- [One filled example per section type](#one-filled-example-per-section-type)
- [Manifest and releases files](#manifest-and-releases-files)
- [Out of scope](#out-of-scope)

## Top-level fields

One JSON object per fragment, one file per fragment.

| Field          | Type          | Required | Rule |
| -------------- | ------------- | -------- | ---- |
| `schema`       | string        | yes      | Exactly `"dev-report-fragment/v1"`. Forward-compat gate. |
| `id`           | string        | yes      | `[a-z0-9-]+`, unique within a release. Filename, nav anchor, cross-release diff key. |
| `category`     | enum          | yes      | One of `architecture`, `evolution`, `dependencies`, `quality`, `security`, `schema`, `contracts`, `mission`, `test-coverage`, `test-reports`, `overview`. |
| `title`        | string        | yes      | Non-empty. Nav label + fragment header. |
| `summary`      | string        | yes      | One line, plain text, no markdown. May be empty string but the key is required. |
| `status`       | enum          | yes      | `ok`, `info`, `warn`, `error`. Drives the badge and roll-up. |
| `severity`     | number\|null  | no       | 0–100. Finer ordering within `warn`/`error`. |
| `producer`     | object        | yes      | `{ "skill", "tool", "version" }` — all three non-empty strings. |
| `generated_at` | string        | yes      | Non-empty ISO-8601 UTC. Display only, not the release identity. |
| `metrics`      | object        | no       | Flat `string → number` map. The cross-release diff surface. |
| `body`         | array         | yes      | Ordered typed sections. May be empty but the key is required. |

A duplicate `id` across two files in the same staging dir is a validation
failure.

## metrics is a flat number map

`metrics{}` is deliberately flat — every value is a number. Flatness makes
release-over-release diffing renderer-agnostic: the split-screen computes
`current.metrics[k] - previous.metrics[k]` for every shared key. Units,
labels, and good-direction are **not** in `metrics`; they live in
`metric-cards`, so one number is both diffable and presentable. A non-numeric
metric value fails validation.

The producer's script writes the factual `metrics{}` and factual `body[]`.
The producer Skill's `*-synthesis.md` role enriches `summary` and adds
narrative `body[]`. The merged object is what is validated.

## Body section types

Each `body[]` element is
`{ "type": <enum>, "title"?: <string>, "view"?: "release\|delta",
"files"?: [...], …type fields }`. Ten types in v1; the renderer has exactly
one function per type.

| `type`         | Required shape (beyond `type`/`title`) |
| -------------- | -------------------------------------- |
| `markdown`     | `md: string` (GitHub-flavored, sanitized before injection). |
| `table`        | `columns:[{key,label,type:"string\|number\|file",sortable?}]`, `rows:[obj]`; optional `filterable`, `defaultSort:{key,dir}`. `columns` non-empty. A row MAY carry `children:[row,…]` (recursive, expandable). A `type:"file"` column's cell value is a path string resolved against the section's `files[]`. |
| `key-value`    | `pairs:[{k,v}]`, non-empty. |
| `metric-cards` | `cards:[{label,value,unit?,delta_metric?}]`, non-empty. `delta_metric` links a card to a `metrics` key for the split-screen ▲/▼. |
| `d3-graph`     | `nodes:[{id,label?,group?}]` (non-empty), `links:[{source,target,value?}]`, `layout:"force\|dag\|chord"`. |
| `sankey`       | `nodes:[{id,label?}]` (non-empty), `links:[{source,target,value}]` (non-empty). |
| `treemap`      | `root:{name,children?,value?}` — `root.name` required. |
| `heatmap`      | `xLabels:[]` (non-empty), `yLabels:[]` (non-empty), `cells:[{x,y,v}]`, `colorScale:"sequential\|diverging"`. |
| `mermaid`      | `diagram: string`. |
| `image`        | `src: string` (a `data:image/…;base64,…` URI, standalone-safe, or a relative `assets/…` path), `alt: string`; optional `title`. |

An unrecognized `type` is **not** a validation failure: it renders a visible
"unsupported section type `X`" placeholder. The contract is
forward-compatible by design — only the ten known types have their inner
shape checked.

### `view` — which column a section lands in (section-level)

Every fragment renders as two fixed side-by-side columns: a left **This
release** column and a right **Δ vs previous** column. A section MAY carry
`"view": "release" | "delta"`; **absent ⇒ `"release"`**. Release-view
sections fill the left column in `body[]` order; delta-view sections fill the
right column in `body[]` order. A column with no sections shows a muted
`— nothing for this view —` placeholder. If present, `view` must be exactly
`"release"` or `"delta"` (any other value fails validation). Untagged
fragments are backward-compatible: every section lands left and still
validates. This two-column structure is permanent and is distinct from the
show/hide-previous-releases toggle.

### `files[]` — producer-embedded file excerpts (section-level)

A section MAY include
`"files": [ { "path": str, "lang": str, "excerpt": str, "startLine"?: int } ]`.
Each entry's `path`, `lang`, and `excerpt` are required strings (`excerpt`
may be empty); `startLine`, if present, is an integer. Excerpts are
producer-embedded — the build never reads files. Any path string that matches
a `files[].path` in the **same section** renders as a clickable token (e.g. a
`table` `type:"file"` cell); clicking opens a modal that renders the excerpt
via marked+DOMPurify when `lang` is `md`/`markdown`, otherwise in an escaped
monospace `<pre>` labeled with the lang and optional start line. The modal
includes an "Open full file" affordance that is inert under `file://` (it
needs a served report). `files[]` shape is validated if present.

### `table` row `children` — expandable subrows

A `table` row MAY include `"children": [row, …]` (recursive). Rows with
children get a `▸`/`▾` disclosure toggle, collapsed by default; children are
indented one level. Filtering keeps a row if it or any descendant matches
(ancestors shown). Sorting applies within each level. `children`, if present,
must be an array; nested rows are validated recursively.

## One filled example per section type

```json
{ "type": "markdown", "title": "Summary",
  "md": "Three cycles detected. The `auth ↔ billing` cycle is the highest risk." }
```

```json
{ "type": "table", "title": "Cycles", "filterable": true,
  "columns": [ {"key":"members","label":"Members","type":"string","sortable":true},
               {"key":"length","label":"Length","type":"number","sortable":true} ],
  "rows": [ {"members":"auth → billing → auth","length":2} ],
  "defaultSort": {"key":"length","dir":"desc"} }
```

```json
{ "type": "key-value", "title": "Provenance",
  "pairs": [ {"k":"Resolver","v":"node"}, {"k":"Lockfile","v":"present"} ] }
```

```json
{ "type": "metric-cards", "cards": [
  { "label": "Modules", "value": 214, "delta_metric": "node_count" },
  { "label": "Median build", "value": 92, "unit": "s", "delta_metric": "build_seconds" } ] }
```

```json
{ "type": "d3-graph", "title": "Module graph", "layout": "dag",
  "nodes": [ {"id":"auth","label":"auth","group":"core"},
             {"id":"billing","label":"billing","group":"core"} ],
  "links": [ {"source":"auth","target":"billing","value":4} ] }
```

```json
{ "type": "sankey", "title": "Import flow",
  "nodes": [ {"id":"a","label":"auth"}, {"id":"c","label":"core"} ],
  "links": [ {"source":"a","target":"c","value":5} ] }
```

```json
{ "type": "treemap", "title": "Churn by area",
  "root": { "name": "repo", "children": [
    { "name": "src/api", "value": 90 },
    { "name": "src/ui", "value": 40 } ] } }
```

```json
{ "type": "heatmap", "title": "Author × area",
  "xLabels": ["api","ui"], "yLabels": ["alice","bob"],
  "colorScale": "sequential",
  "cells": [ {"x":"api","y":"alice","v":30}, {"x":"ui","y":"bob","v":8} ] }
```

```json
{ "type": "mermaid", "title": "Release flow",
  "diagram": "graph LR; commit-->review-->merge-->release" }
```

```json
{ "type": "image", "title": "Overview",
  "src": "data:image/svg+xml;base64,PHN2Zy8+",
  "alt": "Release overview infographic" }
```

A `delta`-view section (lands in the right **Δ vs previous** column):

```json
{ "type": "metric-cards", "view": "delta", "title": "Since last release",
  "cards": [ { "label": "New cycles", "value": 1, "delta_metric": "cycle_count" } ] }
```

A section with `files[]` and a `table` whose `type:"file"` column resolves to
those excerpts:

```json
{ "type": "table", "title": "Touched files",
  "files": [ { "path": "src/auth.ts", "lang": "ts",
               "excerpt": "export function login() {}", "startLine": 12 } ],
  "columns": [ {"key":"file","label":"File","type":"file"},
               {"key":"lines","label":"Lines","type":"number","sortable":true} ],
  "rows": [ {"file":"src/auth.ts","lines":48} ] }
```

A `table` with expandable nested `children`:

```json
{ "type": "table", "title": "Suite results", "filterable": true,
  "columns": [ {"key":"name","label":"Test","type":"string","sortable":true},
               {"key":"ms","label":"ms","type":"number","sortable":true} ],
  "rows": [ { "name": "auth suite", "ms": 120, "children": [
               { "name": "login ok", "ms": 40 },
               { "name": "login fail", "ms": 80 } ] } ] }
```

A complete fragment with all required top-level fields and a body of these
sections is the self-consistency check `validate_fragments.py` enforces.

## Manifest and releases files

`dev-report-build` derives these — a producer never writes them.

`data/manifest.json` per release:

```json
{
  "schema": "dev-report-manifest/v1",
  "release": { "id": "2026.05.0", "vcs_ref": "v2026.05.0",
               "git_sha": "9f3c1a7", "created_at": "2026-05-17T09:30:00Z",
               "label": "May 2026 release", "commit_count": 96 },
  "rollup": { "ok": 12, "info": 3, "warn": 4, "error": 1 },
  "categories": [
    { "id": "dependencies", "label": "Dependencies", "fragments": [
      { "id": "dependency-graph", "title": "Internal dependency graph",
        "summary": "214 modules, 3 cycles, max depth 7.",
        "status": "warn", "severity": 40,
        "path": "data/dependencies/dependency-graph.json" } ] } ]
}
```

`reports/releases.json` (top-level, newest-first, upserted by `id`):

```json
{
  "schema": "dev-report-releases/v1",
  "releases": [
    { "id": "2026.05.0", "vcs_ref": "v2026.05.0", "git_sha": "9f3c1a7",
      "created_at": "2026-05-17T09:30:00Z", "label": "May 2026",
      "commit_count": 96, "path": "2026.05.0/" }
  ]
}
```

`commit_count` is `null` when `dev-report-build` is run without `--commits`.
The renderer formats the report title as `<created_at date> Release: N
commits` (the `: N commits` clause is omitted when `commit_count` is null).

A fragment with `category:"overview"` is pinned **first** in the left nav and
is the default page on initial load when one is present; if there are several,
the lexically-first `id` is the landing fragment. It renders like any other
fragment.

## Out of scope

Choosing `summary` wording or narrative `body[]` content (a producer Skill's
`*-synthesis.md` role does that). HTML, JS, D3, or how a section renders (the
framework owns rendering — a producer dispatches on nothing). DB schema diffs
or any tool-specific raw format (normalized away before a fragment exists).
