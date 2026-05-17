# Body section types — rendered behavior

What each of the ten `body[]` types looks like once the framework renders it,
and the minimum fields each needs. Use this when deciding which section type
carries a given fact. The authoritative field rules are in
[fragment-schema.md](fragment-schema.md).

## Contents

- [Two-column release/delta view](#two-column-releasedelta-view)
- [markdown](#markdown)
- [table](#table)
- [key-value](#key-value)
- [metric-cards](#metric-cards)
- [d3-graph](#d3-graph)
- [sankey](#sankey)
- [treemap](#treemap)
- [heatmap](#heatmap)
- [mermaid](#mermaid)
- [image](#image)
- [File preview](#file-preview)
- [Unknown types](#unknown-types)
- [Out of scope](#out-of-scope)

## Two-column release/delta view

Every fragment renders as two fixed side-by-side columns regardless of which
release is shown: a left column headed **This release** and a right column
headed **Δ vs previous**. A section's optional `"view"` tag (`"release"` or
`"delta"`, absent ⇒ `"release"`) decides its column; sections keep `body[]`
order within their column. An empty column shows a muted
`— nothing for this view —` placeholder. This is permanent fragment structure
and is separate from the sidebar's show/hide-previous-releases toggle.

```json
{ "type": "metric-cards", "view": "delta", "title": "Since last release",
  "cards": [ { "label": "New cycles", "value": 1, "delta_metric": "cycle_count" } ] }
```

## markdown

Renders GitHub-flavored markdown to sanitized HTML (marked → DOMPurify). Use
for narrative, summaries, and prose findings. Never inject HTML you want
preserved — DOMPurify strips scripts and event handlers.

```json
{ "type": "markdown", "title": "Summary",
  "md": "Three cycles detected. The `auth ↔ billing` cycle is the highest risk." }
```

Renders as a prose block; backticked spans become inline code, fenced blocks
become `<pre>`.

## table

Sortable, optionally filterable table over a flat row array. Click a sortable
column header to toggle ascending/descending; the filter box does a
case-insensitive substring match across all columns. `defaultSort` sets the
initial order.

```json
{ "type": "table", "title": "Cycles", "filterable": true,
  "columns": [ {"key":"members","label":"Members","type":"string","sortable":true},
               {"key":"length","label":"Length","type":"number","sortable":true} ],
  "rows": [ {"members":"auth → billing → auth","length":2} ],
  "defaultSort": {"key":"length","dir":"desc"} }
```

`type:"number"` sorts numerically; `type:"string"` sorts lexically.

A row MAY carry `children:[row,…]` (recursive). Parent rows get a `▸`/`▾`
disclosure, collapsed by default; children indent one level. The filter keeps
a row if it or any descendant matches (ancestors stay visible); sorting
applies within each level.

```json
{ "type": "table", "title": "Suite results", "filterable": true,
  "columns": [ {"key":"name","label":"Test","type":"string","sortable":true},
               {"key":"ms","label":"ms","type":"number","sortable":true} ],
  "rows": [ { "name": "auth suite", "ms": 120, "children": [
               { "name": "login ok", "ms": 40 },
               { "name": "login fail", "ms": 80 } ] } ] }
```

A column with `type:"file"` renders its cell as a clickable token when the
value matches a `files[].path` on the same section (see
[File preview](#file-preview)).

## key-value

A two-column definition list for short labeled facts (provenance, config
snapshots). No sorting, no filtering — use `table` if either is needed.

```json
{ "type": "key-value", "title": "Provenance",
  "pairs": [ {"k":"Resolver","v":"node"}, {"k":"Lockfile","v":"present"} ] }
```

## metric-cards

Big-number tiles. `unit` is appended after the value. `delta_metric` ties a
card to a `metrics` key so split-screen shows an inline ▲/▼ against the
comparison release.

```json
{ "type": "metric-cards", "cards": [
  { "label": "Modules", "value": 214, "delta_metric": "node_count" },
  { "label": "Median build", "value": 92, "unit": "s", "delta_metric": "build_seconds" } ] }
```

The card value is shown verbatim; the diff is computed from `metrics`, not the
card, so set both.

## d3-graph

Node-link graph on raw D3. `layout` is one of `force` (force-directed),
`dag` (layered), or `chord` (circular: nodes become arcs around a ring,
`links[].value` becomes ribbon thickness via a node×node matrix). An unknown
`layout` falls back to `force`. `links.source`/`links.target` reference
`nodes.id`. `group` colors nodes; `value` weights link width (force/dag) or
ribbon thickness (chord). `chord` is a `layout` value, not a tenth body
type — the contract stays nine types.

```json
{ "type": "d3-graph", "title": "Module graph", "layout": "dag",
  "nodes": [ {"id":"auth","label":"auth","group":"core"},
             {"id":"billing","label":"billing","group":"core"} ],
  "links": [ {"source":"auth","target":"billing","value":4} ] }
```

## sankey

Flow diagram (d3-sankey). Every link needs a numeric `value`; band width is
proportional to it. Good for import flow, data flow, dependency volume.

```json
{ "type": "sankey", "title": "Import flow",
  "nodes": [ {"id":"a","label":"auth"}, {"id":"c","label":"core"} ],
  "links": [ {"source":"a","target":"c","value":5} ] }
```

## treemap

Nested rectangles sized by `value`. Leaf `value` drives area; parents sum
their children. Use for size/share-of-total (LOC by area, churn by directory).

```json
{ "type": "treemap", "title": "Churn by area",
  "root": { "name": "repo", "children": [
    { "name": "src/api", "value": 90 },
    { "name": "src/ui", "value": 40 } ] } }
```

## heatmap

Matrix of `cells` indexed by `xLabels`/`yLabels`. `colorScale:"sequential"`
for one-directional magnitude, `"diverging"` for signed values around zero.
Cells reference labels by string, not index.

```json
{ "type": "heatmap", "title": "Author × area",
  "xLabels": ["api","ui"], "yLabels": ["alice","bob"],
  "colorScale": "sequential",
  "cells": [ {"x":"api","y":"alice","v":30}, {"x":"ui","y":"bob","v":8} ] }
```

## mermaid

Client-side Mermaid render of a diagram string. Use for sequence/flow/state
diagrams that are authored, not data-derived. A render failure shows an inline
placeholder, never an empty section.

```json
{ "type": "mermaid", "title": "Release flow",
  "diagram": "graph LR; commit-->review-->merge-->release" }
```

## image

A single `<img>` constrained to the content width. `src` is either a
self-contained `data:image/…;base64,…` URI (standalone-safe, survives the
`file://` embed) or a relative `assets/…` path; `alt` is the accessible text;
optional `title` becomes the tooltip. Used for the Overview infographic.

```json
{ "type": "image", "title": "Overview",
  "src": "data:image/svg+xml;base64,PHN2Zy8+",
  "alt": "Release overview infographic" }
```

## File preview

A section's optional
`files:[{path,lang,excerpt,startLine?}]` carries producer-embedded source
excerpts (the build never reads files). Any path string that matches a
`files[].path` on the same section becomes a clickable token — most often a
`table` `type:"file"` cell. Clicking opens a modal: `lang` `md`/`markdown`
renders the excerpt via marked+DOMPurify, anything else shows an escaped
monospace `<pre>` labeled with the lang and optional start line. An "Open full
file" affordance is active only when the report is served; under `file://` it
is inert and says so.

```json
{ "type": "table", "title": "Touched files",
  "files": [ { "path": "src/auth.ts", "lang": "ts",
               "excerpt": "export function login() {}", "startLine": 12 } ],
  "columns": [ {"key":"file","label":"File","type":"file"},
               {"key":"lines","label":"Lines","type":"number","sortable":true} ],
  "rows": [ {"file":"src/auth.ts","lines":48} ] }
```

## Unknown types

Any `type` outside the ten renders a visible
"unsupported section type `X` (fragment `id`)" placeholder and never throws.
This is the forward-compat guarantee: a newer producer can emit a type an
older deployed report does not know, and the rest of the report still renders.

## Out of scope

Inventing an eleventh type (the renderer only dispatches the ten; a new type
is a contract change, not a fragment change). Styling overrides — color, size,
and layout are the framework's, not the fragment's.
