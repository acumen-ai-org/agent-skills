# Body section types — rendered behavior

What each of the nine `body[]` types looks like once the framework renders it,
and the minimum fields each needs. Use this when deciding which section type
carries a given fact. The authoritative field rules are in
[fragment-schema.md](fragment-schema.md).

## Contents

- [markdown](#markdown)
- [table](#table)
- [key-value](#key-value)
- [metric-cards](#metric-cards)
- [d3-graph](#d3-graph)
- [sankey](#sankey)
- [treemap](#treemap)
- [heatmap](#heatmap)
- [mermaid](#mermaid)
- [Unknown types](#unknown-types)
- [Out of scope](#out-of-scope)

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

Force-directed (`layout:"force"`) or layered (`layout:"dag"`) node-link graph
on raw D3. `links.source`/`links.target` reference `nodes.id`. `group` colors
nodes; `value` weights link width.

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

## Unknown types

Any `type` outside the nine renders a visible
"unsupported section type `X` (fragment `id`)" placeholder and never throws.
This is the forward-compat guarantee: a newer producer can emit a type an
older deployed report does not know, and the rest of the report still renders.

## Out of scope

Inventing a tenth type (the renderer only dispatches the nine; a new type is a
contract change, not a fragment change). Styling overrides — color, size, and
layout are the framework's, not the fragment's.
