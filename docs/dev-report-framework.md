# Dev-report Framework

The contract and rendering model for `dev-report-framework` — the Skill that
aggregates report fragments from every `dev-analysis-`/`dev-test-` Skill into
one navigable, standalone HTML report folder per release, with a
this-release-vs-previous split-screen.

The report-fragment JSON is the **only** coupling between producers and the
framework. A producer Skill emits valid fragments and knows nothing about
HTML, JS, or D3. The framework renders any fragment generically by dispatching
on `body[].type`, so a new `dev-analysis-` Skill needs zero framework changes.

## Contents

- [Report-fragment contract](#report-fragment-contract)
- [Body section types](#body-section-types)
- [Filled example](#filled-example)
- [Folder layout](#folder-layout)
- [Release identity](#release-identity)
- [The file:// problem and the embed mitigation](#the-file-problem-and-the-embed-mitigation)
- [CDN libraries](#cdn-libraries)
- [Split-screen model](#split-screen-model)
- [dev-report-build](#dev-report-build)
- [validate_fragments.py](#validate_fragmentspy)

## Report-fragment contract

One JSON file per fragment. A producer Skill emits one or more. The formal
schema is enforced by `validate_fragments.py`; this table is its meaning.

| Field          | Type          | Required | Notes |
| -------------- | ------------- | -------- | ----- |
| `schema`       | string        | yes      | Contract version. `"dev-report-fragment/v1"`. Forward-compat gate. |
| `id`           | string        | yes      | `[a-z0-9-]+`, unique within a release. Filename, nav anchor, and the cross-release diff key. |
| `category`     | enum          | yes      | One of `architecture \| evolution \| dependencies \| quality \| security \| schema \| contracts \| mission`. Drives left-nav grouping. |
| `title`        | string        | yes      | Human label in nav + fragment header. |
| `summary`      | string        | yes      | One line, plain text (no markdown). Nav tooltip + overview row. |
| `status`       | enum          | yes      | `ok \| info \| warn \| error`. Drives the badge and overview roll-up. |
| `severity`     | number\|null  | no       | 0–100. Optional finer ordering within `warn`/`error`. |
| `producer`     | object        | yes      | `{ "skill": "...", "tool": "...", "version": "..." }`. Provenance, shown in the fragment footer. |
| `generated_at` | string        | yes      | ISO-8601 UTC. Display only — not the release identity. |
| `metrics`      | object        | no       | Flat `string → number` map. The cross-release diff surface (see below). |
| `body`         | array         | yes      | Ordered typed sections (see [Body section types](#body-section-types)). |

`metrics{}` is deliberately a flat map of numbers. Flatness makes
release-over-release diffing trivial and renderer-agnostic: the split-screen
computes `current.metrics[k] - previous.metrics[k]` for every shared key.
Units, labels, and good-direction are **not** in `metrics` — they live in
`metric-cards` and the manifest, so a number can be both diffable and pretty.

The producer's script writes the factual `metrics{}` and factual `body[]`. The
producer Skill's `*-synthesis.md` role enriches `summary` and adds narrative
`body[]` sections. The merged result is what gets validated.

## Body section types

Each `body[]` element is `{ "type": <enum>, "title"?: <string>, ...type fields }`.
The renderer has exactly one function per type. Nine types in v1:

| `type`         | Shape (beyond `type`/`title`) | Renders as |
| -------------- | ----------------------------- | ---------- |
| `markdown`     | `md: string` (GitHub-flavored) | Sanitized HTML. |
| `table`        | `columns:[{key,label,type:"string\|number",sortable?}], rows:[obj], filterable?, defaultSort?:{key,dir}` | Sortable/filterable table. |
| `key-value`    | `pairs:[{k,v}]` | Definition list. |
| `metric-cards` | `cards:[{label,value,unit?,delta_metric?}]` | Big-number tiles. `delta_metric` links a card to a `metrics` key so split-screen shows ▲/▼. |
| `d3-graph`     | `nodes:[{id,label,group?}], links:[{source,target,value?}], layout:"force\|dag"` | Force or layered DAG. |
| `sankey`       | `nodes:[{id,label}], links:[{source,target,value}]` | Flow diagram. |
| `treemap`      | `root:{name,children?,value?}` | Hierarchical size. |
| `heatmap`      | `xLabels:[], yLabels:[], cells:[{x,y,v}], colorScale:"sequential\|diverging"` | Matrix heatmap. |
| `mermaid`      | `diagram: string` | Client-side `mermaid.render`. |

An unrecognized `type` renders a visible "unsupported section type `X`
(fragment `id`)" placeholder. It never fails the build — the contract is
forward-compatible by design.

## Filled example

`reports/2026.05.0/data/dependencies/dependency-graph.json`:

```json
{
  "schema": "dev-report-fragment/v1",
  "id": "dependency-graph",
  "category": "dependencies",
  "title": "Internal dependency graph",
  "summary": "214 modules, 3 cycles, max depth 7.",
  "status": "warn",
  "severity": 40,
  "producer": { "skill": "dev-analysis-dependencies", "tool": "depcruise", "version": "16.3.0" },
  "generated_at": "2026-05-17T09:12:44Z",
  "metrics": { "node_count": 214, "edge_count": 588, "cycle_count": 3, "max_depth": 7 },
  "body": [
    { "type": "metric-cards", "cards": [
      { "label": "Modules", "value": 214, "delta_metric": "node_count" },
      { "label": "Cycles", "value": 3, "delta_metric": "cycle_count" }
    ]},
    { "type": "markdown", "title": "Summary",
      "md": "Three cycles detected. The `auth ↔ billing` cycle is the highest risk." },
    { "type": "d3-graph", "title": "Module graph", "layout": "dag",
      "nodes": [ {"id":"auth","label":"auth","group":"core"},
                 {"id":"billing","label":"billing","group":"core"} ],
      "links": [ {"source":"auth","target":"billing","value":4},
                 {"source":"billing","target":"auth","value":1} ] },
    { "type": "table", "title": "Cycles", "filterable": true,
      "columns": [ {"key":"members","label":"Members","type":"string","sortable":true},
                   {"key":"length","label":"Length","type":"number","sortable":true} ],
      "rows": [ {"members":"auth → billing → auth","length":2} ],
      "defaultSort": {"key":"length","dir":"desc"} }
  ]
}
```

Every required field is present, `category` is in the enum, and all four
`body[]` types are in the supported set — the self-consistency check the
report's `validate_fragments.py` enforces.

## Folder layout

```
reports/
├── releases.json                       # newest-first; build upserts by id
└── <release-id>/                       # id = explicit CLI arg, [A-Za-z0-9._-]+
    ├── index.html                      # the shell; identical bytes per release
    ├── assets/
    │   ├── app.js                      # generic renderer (copied verbatim)
    │   └── app.css                     # chrome/layout/status colors
    └── data/
        ├── manifest.json               # nav tree + rollup + release identity
        └── <category>/<fragment-id>.json
```

`assets/app.js|app.css` are copied verbatim from the Skill's
`scripts/assets/` into every release so the folder opens with no dependency on
the repo. `data/*.json` is always written (diffable in git, re-buildable) even
when it is also inlined into `index.html` (see below).

`data/manifest.json` per release:

```json
{
  "schema": "dev-report-manifest/v1",
  "release": { "id": "2026.05.0", "vcs_ref": "v2026.05.0",
               "git_sha": "9f3c1a7", "created_at": "2026-05-17T09:30:00Z",
               "label": "May 2026 release" },
  "rollup": { "ok": 12, "info": 3, "warn": 4, "error": 1 },
  "categories": [
    { "id": "dependencies", "label": "Dependencies", "fragments": [
      { "id": "dependency-graph", "title": "Internal dependency graph",
        "summary": "214 modules, 3 cycles, max depth 7.",
        "status": "warn", "severity": 40,
        "path": "data/dependencies/dependency-graph.json" } ] }
  ]
}
```

The shell reads `manifest.json` first, renders the nav, then loads each
fragment on demand. Categories with no fragments are omitted from the nav.

`reports/releases.json` (top-level, newest-first) drives prev/next navigation:

```json
{
  "schema": "dev-report-releases/v1",
  "releases": [
    { "id": "2026.05.0", "vcs_ref": "v2026.05.0", "git_sha": "9f3c1a7",
      "created_at": "2026-05-17T09:30:00Z", "label": "May 2026", "path": "2026.05.0/" },
    { "id": "2026.04.0", "vcs_ref": "v2026.04.0", "git_sha": "1b2d4e8",
      "created_at": "2026-04-12T08:00:00Z", "label": "April 2026", "path": "2026.04.0/" }
  ]
}
```

`dev-report-build` reads, upserts by `id`, and rewrites this file atomically on
every build.

## Release identity

A release is identified by an explicit caller-supplied `release-id` (the first
positional CLI arg), constrained to `[A-Za-z0-9._-]+` so it is a safe
directory name on every platform. The build auto-captures
`git rev-parse --short HEAD` and the UTC timestamp as metadata; `--vcs-ref`
records a tag/branch when supplied, else `null`.

Explicit ids are chosen over `git describe` because reports are often built
before a tag exists (pre-tag CI), two builds can land on the same date, and a
raw SHA is unreadable in navigation. The id is human-meaningful and stable;
provenance is never lost because the SHA and timestamp are captured regardless.

## The file:// problem and the embed mitigation

Opening `index.html` via `file://` and `fetch('data/manifest.json')` fails in
Chromium-based browsers and is inconsistent in Safari: the `file://` origin is
opaque, so same-origin policy blocks reading sibling files. A naive
fetch-based loader shows an empty report on double-click. This is the single
biggest implementation risk and the reason for the mitigation below.

`dev-report-build` inlines the manifest and every fragment into `index.html`
as one `<script id="report-data" type="application/json">…</script>` data
island (the default). The loader's accessor is:

```
getData(path):
  if window.__REPORT_DATA__[path] exists → return it      (embedded; file:// safe)
  else → fetch(path)                                       (served mode)
```

Default builds embed everything, so the folder works by double-click with zero
server and zero CORS. `data/*.json` is still written for git-diffability and
re-builds. `--no-embed` skips inlining for very large reports meant to be
served; in that mode the folder is viewed with a static server, e.g.:

```
python3 -m http.server --directory reports/2026.05.0
```

Data islands (`<script type="application/json">`) are universally supported
and sidestep CORS entirely — the boring, proven choice. The trade-off is
`index.html` size for very large reports, which `--no-embed` covers.

## CDN libraries

Pinned versions with SRI hashes in `index.html`. One renderer per concern, no
build step:

| Need          | Library                         | Why |
| ------------- | ------------------------------- | --- |
| Markdown      | marked + DOMPurify              | De-facto standard; `md` is sanitized before injection. |
| Visualization | D3 v7 + d3-sankey               | One dependency covers graph/sankey/treemap/heatmap. Renderers hand-rolled on raw D3 for consistency. |
| Diagrams      | Mermaid                         | Direct match for the `mermaid` section type; renders client-side. |
| Tables        | hand-rolled (no library)        | Sort/filter on a JSON array is ~120 lines of vanilla JS; avoids dragging in jQuery/DataTables. |

CDN libs require network on first open (the browser caches afterward). This is
documented in the Skill; vendoring libraries into `assets/` is a future
option, not part of v1.

## Split-screen model

- **Left nav** is built from `manifest.json`: categories → fragments, a status
  dot per fragment, a roll-up badge per category. The URL hash
  (`#dependencies/dependency-graph`) deep-links and drives the back button.
- A **single/split toggle** switches between current-release-only and two
  side-by-side panes showing the same fragment `id`.
- In split mode the right pane has `◀ ▶` controls (and left/right arrow keys
  when the report has focus) that walk `releases.json`; entries after the
  current one are older. The right pane loads
  `../<prev-release>/data/<category>/<fragment-id>.json` — a sibling-folder
  relative path that works because all releases sit under `reports/`.
- If a fragment `id` is absent in the previous release, the right pane shows a
  "not present in `<release>`" placeholder (a newly added analyzer is handled
  gracefully).
- When both panes show the same fragment, a Δ table is computed from shared
  `metrics{}` keys (value, value, delta, %), and `metric-cards` with a
  `delta_metric` show an inline ▲/▼.

`app.js` is a single hand-written classic script — no bundler, no npm. The
renderer is a `switch(section.type)` dispatch table.

## dev-report-build

```
dev-report-build <release-id> <fragments-dir> <reports-root> [--vcs-ref REF] [--label TEXT] [--no-embed]
```

| Arg              | Meaning |
| ---------------- | ------- |
| `<release-id>`   | Explicit id, validated `[A-Za-z0-9._-]+`. Becomes the folder name. |
| `<fragments-dir>`| Staging dir of `*.json` fragments. The script reads each fragment's `category` and lays it out under `data/<category>/`. |
| `<reports-root>` | The `reports/` dir to write into and update. |
| `--vcs-ref`      | Optional tag/branch recorded in the manifests. |
| `--label`        | Optional human label; defaults to `<release-id>`. |
| `--no-embed`     | Skip inlining data into `index.html` (served mode, large reports). |

Behavior: validate every fragment (same logic as `validate_fragments.py`);
build into a temp dir and move into place only on success (atomic); auto-capture
short SHA (best-effort — warn, do not fail, if not a git repo) and UTC
timestamp; lay fragments out by `category`; compute `rollup`; write
`manifest.json`; copy `assets/*`; inline data unless `--no-embed`; upsert the
release into `releases.json` and rewrite atomically. Python 3, standard library
only.

Exit codes:

| Code | Meaning |
| ---- | ------- |
| `0`  | Report folder written; `releases.json` updated. |
| `1`  | Bad arguments / usage. |
| `2`  | I/O failure (unwritable `reports-root`, unreadable `fragments-dir`). |
| `3`  | One or more fragments failed contract validation — nothing written. |

## validate_fragments.py

```
validate_fragments.py <fragments-dir>
```

The standalone feedback-loop validator a producer Skill runs **before**
handing fragments to the build: exit `0` when every fragment conforms, exit `3`
with a per-file error list on stderr otherwise. It is the same validation
`dev-report-build` runs internally — a producer can iterate
"validate → fix → repeat" without invoking a full build. Python 3, standard
library only.
