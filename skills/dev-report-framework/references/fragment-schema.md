# Report-fragment contract (dev-report-fragment/v1)

The single source of truth for the JSON a producer Skill emits. This file
ships inside the Skill so the contract travels with the renderer.
`validate_fragments.py` enforces exactly what is written here.

## Contents

- [Top-level fields](#top-level-fields)
- [metrics is a flat number map](#metrics-is-a-flat-number-map)
- [Body section types](#body-section-types)
- [mermaid is linted at validate time](#mermaid-is-linted-at-validate-time)
- [Menu groups and the top menu](#menu-groups-and-the-top-menu)
- [Modules and the global filter](#modules-and-the-global-filter)
- [One filled example per section type](#one-filled-example-per-section-type)
- [Manifest and releases files](#manifest-and-releases-files)
- [Out of scope](#out-of-scope)

## Top-level fields

One JSON object per fragment, one file per fragment.

| Field          | Type          | Required | Rule |
| -------------- | ------------- | -------- | ---- |
| `schema`       | string        | yes      | Exactly `"dev-report-fragment/v1"`. Forward-compat gate. |
| `id`           | string        | yes      | `[a-z0-9-]+`, unique within a release. Filename, nav anchor, cross-release diff key. |
| `category`     | enum          | yes      | One of `architecture`, `evolution`, `dependencies`, `quality`, `security`, `schema`, `contracts`, `mission`, `test-coverage`, `test-reports`, `overview`, `report`. |
| `title`        | string        | yes      | Non-empty. Nav label + fragment header. |
| `summary`      | string        | yes      | One line, plain text, no markdown. May be empty string but the key is required. |
| `status`       | enum          | yes      | `ok`, `info`, `warn`, `error`. Drives the badge and roll-up. |
| `severity`     | number\|null  | no       | 0–100. Finer ordering within `warn`/`error`. |
| `help`         | string        | no       | Markdown. When non-empty (or any section has `help`) the fragment header shows a `❓` link to a consolidated `help.html` page that explains how to read this report part. Empty string allowed (no link). |
| `producer`     | object        | yes      | `{ "skill", "tool", "version" }` — all three non-empty strings. |
| `generated_at` | string        | yes      | Non-empty ISO-8601 UTC. Display only, not the release identity. Rendered through a shared UTC formatter as `YYYY-MM-DD HH:MM UTC` in the fragment footer and the `🪜` provenance panel. |
| `metrics`      | object        | no       | Flat `string → number` map. The cross-release diff surface. |
| `body`         | array         | yes      | Ordered typed sections. May be empty but the key is required. |

A fragment with `category:"report"` is pinned **second** in the left nav
(after `overview`); every other category sorts lexically after the two pins.

The `producer{}` object and `generated_at` also feed the per-fragment `🪜`
provenance panel: a header toggle reveals Skill, Tool, Version, Generated (the
shared `YYYY-MM-DD HH:MM UTC` formatter), and a `skills/<skill>/` source path.

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
`{ "type": <enum>, "title"?: <string>, "status"?: "ok\|info\|warn\|error",
"help"?: <string>, "view"?: "release\|production", "menu"?: <string>,
"module"?: <string>, "files"?: [...], …type fields }`. The renderer has
exactly one function per type.

A section MAY carry `"status"` (one of `ok|info|warn|error`); when set, a
status icon (`✅`/`ℹ️`/`⚠️`/`🚨`) is prepended to the section heading. A
section with neither `title` nor `status` stays headerless (unchanged). If
present, `status` must be one of the four values (any other value fails
validation). A section MAY also carry `"help"` (a short string); when set it
becomes the section heading's hover tooltip and is listed under the fragment's
entry on `help.html`. `help` must be a string if present (empty string
allowed). Both are optional and back-compatible.

| `type`         | Required shape (beyond `type`/`title`) |
| -------------- | -------------------------------------- |
| `markdown`     | `md: string` (GitHub-flavored, sanitized before injection). |
| `table`        | `columns:[{key,label,type:"string\|number\|file\|module\|link",sortable?}]`, `rows:[obj]`; optional `filterable`, `defaultSort:{key,dir}`. `columns` non-empty. A row MAY carry `children:[row,…]` (recursive, expandable). A `type:"file"` column's cell value is a path string resolved against the section's `files[]`. A `type:"module"` column's cell value is an opaque module-id string the global filter matches on. A `type:"link"` column's cell value is `{ "text", "href" }`, a list of those (comma-joined), or a plain string (rendered as text); each `{text,href}` becomes a `target=_blank rel=noopener` anchor. |
| `key-value`    | `pairs:[{k,v}]`, non-empty. |
| `metric-cards` | `cards:[{label,value,unit?,delta_metric?}]`, non-empty. `delta_metric` links a card to a `metrics` key for the split-screen ▲/▼. |
| `d3-graph`     | `nodes:[{id,label?,group?}]` (non-empty), `links:[{source,target,value?}]`, `layout:"force\|dag\|chord"`. |
| `sankey`       | `nodes:[{id,label?}]` (non-empty), `links:[{source,target,value}]` (non-empty). |
| `treemap`      | `root:{name,children?,value?}` — `root.name` required. |
| `heatmap`      | `xLabels:[]` (non-empty), `yLabels:[]` (non-empty), `cells:[{x,y,v}]`, `colorScale:"sequential\|diverging"`. |
| `mermaid`      | `diagram: string`. Linted at validate time (a structural mermaid lint, see [mermaid lint](#mermaid-is-linted-at-validate-time)). |
| `image`        | `src: string` (a `data:image/…;base64,…` URI, standalone-safe, or a relative `assets/…` path), `alt: string`; optional `title`. |
| `diff-view`    | `perspectives:[{slug,title,lead,items}]`, non-empty. `slug` `[a-z0-9-]+`; `title`/`lead` non-empty strings; `items:[{before,after}]` non-empty, each a string pair. An item with both `before` and `after` empty is invalid. Renders a grouped before/after word-diff table. |

An unrecognized `type` is **not** a validation failure: it renders a visible
"unsupported section type `X`" placeholder. The contract is
forward-compatible by design — only the known types have their inner shape
checked.

### mermaid is linted at validate time

A `mermaid` section's `diagram` string is structurally linted by
`validate_fragments.py` (a deterministic, dependency-free check: a known
diagram header, a direction token for `flowchart`/`graph`, balanced
brackets/quotes and `subgraph`/`end`, no reserved bare node id, no stray
fences, content after the header). A diagram that fails the lint is a normal
validation error, so `dev-report-build` refuses to ship a broken diagram
instead of silently rendering an empty panel. A fragment with no `mermaid`
section is unaffected. A deeper true-parse pass via mermaid-cli is available
out-of-band through the standalone `scripts/verify_mermaid.py` tool; it is not
part of the validate-time gate (no dependency is required to validate).

### `view` — which column a section lands in (section-level)

Every fragment renders as two fixed side-by-side columns: a left **This
release** column (the state *after* this release) and a right **vs production**
column (the difference this release makes to production — the
release-candidate's diff against the production branch, conceptually the
`production..main` scope). A section MAY carry
`"view": "release" | "production"`; **absent ⇒ `"release"`**. Release-view
sections fill the left column in `body[]` order; production-view sections fill
the right column in `body[]` order. An empty **left** column shows a muted
`— nothing for this view —`. An empty **right** column shows the same string
**only when a production baseline exists**; with no baseline it shows
`No previous production to compare with`. The baseline signal is the embedded
`releases.json`: a baseline exists iff some release entry has an `id` other
than the shown release's id (a build-time snapshot, evaluated under `file://`
without a network read). A producer never emits either placeholder — the
renderer owns the empty-column message. If present, `view` must be exactly
`"release"` or `"production"` (any other value fails validation). Untagged
fragments are backward-compatible: every section lands left and still
validates. This two-column structure is permanent and is distinct from the
show/hide-previous-releases toggle, which is an unrelated cross-release history
feature.

### `menu` — top-menu group label (section-level)

A section MAY carry `"menu": "<label>"`, a non-empty string naming the
top-menu group the section belongs to. If present, `menu` must be a non-empty
string (any other value fails validation). It is the producer's declaration of
how a report part's sections split into named groups.

The top menu is scoped to the **current report part only**. For the displayed
fragment the renderer computes the ordered list of distinct `menu` labels by
**first appearance** across `body[]`. If at least one label exists, the menu
renders those labels in first-appearance order; any sections with no `menu`
are collected under a single leading default item whose label is the
fragment's `title` (or `Overview` if it has none), placed **first**. Selecting
a menu item shows only that group's sections; the first item is selected by
default and the choice is persisted in the URL hash. If the fragment carries
**zero** `menu` labels, no top menu renders and every section shows — fully
backward-compatible. The left nav remains the area → report-part selector; the
top menu is purely intra-part section-group navigation and never lists tools,
fragment ids, or sibling fragments.

Within the selected group the two-column `view` layout, the global `Module:`
filter, file preview, table children, etc. all still apply to the shown
sections. Untagged sections are backward-compatible.

### `module` — module ownership tag (section-level)

A section MAY carry `"module": "<id>"`, a non-empty string. The id is opaque:
the framework never parses or resolves it (`root`, `core`,
`modules/payments` are all just strings to the renderer; resolving them to
paths is a producer concern). A tagged section is hidden whenever the global
module filter is set to a different module; a section with no `module` is
**never** filtered (module-agnostic content always shows). If present,
`module` must be a non-empty string (any other value fails validation).
Untagged sections are backward-compatible. See
[Modules and the global filter](#modules-and-the-global-filter).

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

## Menu groups and the top menu

A report part (one fragment) MAY split its `body[]` sections into named
**menu groups** by tagging sections with `"menu": "<label>"`. The top menu is
producer-declared and scoped strictly to the currently-displayed fragment:

- Distinct `menu` labels are listed in **first-appearance order** across
  `body[]`. Sections with no `menu` collect under one leading default item
  labelled with the fragment's `title` (or `Overview`), placed **first**.
- Selecting a menu item shows only that group's sections; the first item is
  the default. The selection rides in the URL hash so deep links and
  back/forward restore it (an absent/invalid value falls back to the first
  item). Switching the left-nav report part recomputes the menu from the
  newly shown fragment.
- A fragment with **zero** `menu` labels renders no top menu and shows every
  section (legacy behavior). Untagged sections are backward-compatible.

The top menu is intra-part section-group navigation only; it never lists
tools, fragment ids, or sibling fragments. Within the selected group the
two-column `view` layout, the global module filter, file preview, and table
children all still apply.

## Modules and the global filter

A report MAY partition its content by **module** — an opaque producer-defined
id. Three surfaces carry module ids, all optional and all backward-compatible:

- A `body[]` section MAY carry `"module": "<id>"` (non-empty string).
- A `table` column MAY declare `"type": "module"`; each cell in that column
  is a module-id string (empty/absent ⇒ the row is module-agnostic).
- `manifest.json` MAY carry a top-level `"modules": ["<id>", …]`, written
  verbatim by `dev-report-build --modules id1,id2,…` (comma-separated). A
  producer never writes the manifest; the build does.

Module ids are opaque strings. The framework neither parses nor resolves them
— mapping `modules/payments` to a directory is a producer/resolver concern.

The renderer offers one global `Module:` selector (next to the
show/hide-previous-releases control). Its options are `All` ∪
`manifest.modules` ∪ every section `module` value ∪ every `type:"module"`
cell value across all loaded fragments, sorted `All` first, then `root` (if
present), then the rest lexically. Selecting module *M* hides any section
whose `module` is set and ≠ *M*, and in any table with a `type:"module"`
column hides rows whose module cell ≠ *M*; sections with no `module` and rows
with an empty/absent module cell always stay visible. `All` filters nothing.
The selection is carried in the URL hash so deep links and back/forward keep
it, and it composes with the two-column view, the top menu, the
show/hide-previous split, and the table filter. When no module ids exist
anywhere the selector is not rendered — reports that do not use modules look
unchanged.

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

```json
{ "type": "diff-view", "title": "Diff view", "menu": "Diff view",
  "perspectives": [
    { "slug": "user", "title": "User perspective (need)",
      "lead": "What end users see and do.",
      "items": [
        { "before": "",                     "after": "Composition edit-mode panel" },
        { "before": "insertion-order chips", "after": "alphabetical chips" },
        { "before": "Legacy selections",     "after": "" } ] } ] }
```

The single `{ before, after }` pair is the whole item model: `before` empty ⇒
NEW, `after` empty ⇒ DELETED, both set ⇒ UPDATED. Both empty is invalid, and
an empty `items` list is invalid — a perspective with no real items is dropped
by the producer, never emitted empty. The renderer word-diffs each pair when
jsdiff is loaded and falls back to plain text otherwise (a row is never
blank). The item's before/after is the change's own before/after and is
independent of the `view` column tag.

A `production`-view section (lands in the right **vs production** column):

```json
{ "type": "metric-cards", "view": "production", "title": "Change vs production",
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

A section tagged to a module (hidden unless the filter is `All` or `core`):

```json
{ "type": "markdown", "module": "core", "title": "Core notes",
  "md": "Auth and billing both live in the `core` module this release." }
```

A `table` with a `type:"module"` column (rows in `core` and `root`; the
empty-module row is never filtered):

```json
{ "type": "table", "title": "Findings by module",
  "columns": [ {"key":"mod","label":"Module","type":"module"},
               {"key":"finding","label":"Finding","type":"string","sortable":true} ],
  "rows": [ {"mod":"core","finding":"unused export"},
            {"mod":"root","finding":"stale lockfile"},
            {"mod":"","finding":"repo-wide TODO sweep"} ] }
```

Sections split into top-menu groups by `menu` (the untagged `Summary`
collects under the default group labelled with the fragment's `title`, placed
first; then `Graph`, then `Cycles` in first-appearance order):

```json
{ "type": "markdown", "title": "Summary",
  "md": "Orientation across the graph and cycle findings." }
```

```json
{ "type": "d3-graph", "menu": "Graph", "title": "Module graph", "layout": "dag",
  "nodes": [ {"id":"auth","label":"auth"} ], "links": [] }
```

```json
{ "type": "table", "menu": "Cycles", "title": "Cycles",
  "columns": [ {"key":"members","label":"Members","type":"string"} ],
  "rows": [ {"members":"auth → billing → auth"} ] }
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
  "modules": ["root", "core", "modules/payments"],
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

`modules` is the verbatim `--modules id1,id2,…` list (omitted when the flag
is absent). It seeds the global module-filter option set; the build does not
parse or validate the ids.

`commit_count` is `null` when `dev-report-build` is run without `--commits`.
The renderer formats the report title as `YYYY-MM-DD · <release id>` — the
date is the `created_at` date slice and the release id is the version. When
`commit_count` is non-null it renders on a second muted line as `N commits`
(no commit clause in the title itself). A status badge follows the title,
computed from the embedded `releases.json`: it appears **only** when the shown
release is stale — `⚠ superseded — latest is <newest id>` when the shown
release is not `releases[0].id` (newest by `created_at`). The newest release
shows no badge (the absence is the "latest" signal; there is no `✓ latest`
chip).

`dev-report-build` embeds the post-upsert `releases.json` into every
`index.html`'s `<script id="report-data">` data island under the key
`releases.json` (in both embed and `--no-embed` modes — it is tiny), in
addition to the standalone `reports/releases.json`. The renderer reads the
embedded copy first; a `file://` page never fetches, so the badge reflects
the build-time snapshot, while a served report re-reads the live file.

A fragment with `category:"overview"` is pinned **first** in the left nav and
is the default page on initial load when one is present; if there are several,
the lexically-first `id` is the landing fragment. A `category:"report"`
fragment is pinned **second**. All remaining categories sort lexically after
the two pins. Both render like any other fragment.

The left nav groups categories by **area**: `test-coverage` and `test-reports`
collapse under one `Tests` head; every other category is its own area. Each
area head shows the combined fragment count and the worst member status; each
fragment link still routes by its real `category`/`id`.

## Out of scope

Choosing `summary` wording or narrative `body[]` content (a producer Skill's
`*-synthesis.md` role does that). HTML, JS, D3, or how a section renders (the
framework owns rendering — a producer dispatches on nothing). DB schema diffs
or any tool-specific raw format (normalized away before a fragment exists).
