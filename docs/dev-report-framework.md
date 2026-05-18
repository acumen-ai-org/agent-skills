# Dev-report Framework

The contract and rendering model for `dev-report-framework` — the Skill that
aggregates report fragments from every `dev-analysis-`/`dev-test-` Skill into
one navigable, standalone HTML report folder per release, with a permanent
This-release / vs-production two-column layout and a separate
show/hide-previous-releases split-screen.

The report-fragment JSON is the **only** coupling between producers and the
framework. A producer Skill emits valid fragments and knows nothing about
HTML, JS, or D3. The framework renders any fragment generically by dispatching
on `body[].type`, so a new `dev-analysis-` Skill needs zero framework changes.

## Contents

- [Report-fragment contract](#report-fragment-contract)
- [Body section types](#body-section-types)
- [diff-view body type](#diff-view-body-type)
- [mermaid lint and verify_mermaid.py](#mermaid-lint-and-verify_mermaidpy)
- [Module filter](#module-filter)
- [Filled example](#filled-example)
- [Folder layout](#folder-layout)
- [Release identity](#release-identity)
- [The file:// problem and the embed mitigation](#the-file-problem-and-the-embed-mitigation)
- [CDN libraries](#cdn-libraries)
- [Layout, navigation, and split-screen model](#layout-navigation-and-split-screen-model)
- [dev-report-build](#dev-report-build)
- [validate_fragments.py](#validate_fragmentspy)

## Report-fragment contract

One JSON file per fragment. A producer Skill emits one or more. The formal
schema is enforced by `validate_fragments.py`; this table is its meaning.

| Field          | Type          | Required | Notes |
| -------------- | ------------- | -------- | ----- |
| `schema`       | string        | yes      | Contract version. `"dev-report-fragment/v1"`. Forward-compat gate. |
| `id`           | string        | yes      | `[a-z0-9-]+`, unique within a release. Filename, nav anchor, and the cross-release diff key. |
| `category`     | enum          | yes      | One of `architecture \| evolution \| dependencies \| quality \| security \| schema \| contracts \| mission \| test-coverage \| test-reports \| overview \| report`. Drives left-nav grouping; `overview` is pinned first, `report` second, the rest lexical. |
| `title`        | string        | yes      | Human label in nav + fragment header. |
| `summary`      | string        | yes      | One line, plain text (no markdown). Nav tooltip + overview row. |
| `status`       | enum          | yes      | `ok \| info \| warn \| error`. Drives the badge and overview roll-up. |
| `severity`     | number\|null  | no       | 0–100. Optional finer ordering within `warn`/`error`. |
| `help`         | string        | no       | Markdown. Non-empty (or any section `help`) ⇒ a `❓` header link to a consolidated `help.html`. Empty string allowed. |
| `producer`     | object        | yes      | `{ "skill": "...", "tool": "...", "version": "..." }`. Provenance, shown in the fragment footer and the `🪜` panel. |
| `generated_at` | string        | yes      | ISO-8601 UTC. Display only — not the release identity. Rendered as `YYYY-MM-DD HH:MM UTC` via a shared formatter. |
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

Each `body[]` element is
`{ "type": <enum>, "title"?: <string>, "status"?: "ok\|info\|warn\|error",
"help"?: <string>, "view"?: "release\|production", "menu"?: <string>,
"module"?: <string>, "files"?: [...], ...type fields }`.
The renderer has exactly one function per type:

| `type`         | Shape (beyond `type`/`title`) | Renders as |
| -------------- | ----------------------------- | ---------- |
| `markdown`     | `md: string` (GitHub-flavored) | Sanitized HTML. |
| `table`        | `columns:[{key,label,type:"string\|number\|file\|module\|link",sortable?}], rows:[obj], filterable?, defaultSort?:{key,dir}`; a row MAY carry `children:[row,…]` | Sortable/filterable table; rows with `children` are expandable; `type:"file"` cells are clickable file tokens; `type:"module"` cells drive the global module filter; `type:"link"` cells render `{text,href}` (or a list, or plain text) as `target=_blank` anchors. |
| `key-value`    | `pairs:[{k,v}]` | Definition list. |
| `metric-cards` | `cards:[{label,value,unit?,delta_metric?}]` | Big-number tiles. `delta_metric` links a card to a `metrics` key so split-screen shows ▲/▼. |
| `d3-graph`     | `nodes:[{id,label,group?}], links:[{source,target,value?}], layout:"force\|dag\|chord"` | Force, layered DAG, or chord. `chord` is a layout value, not a body type. |
| `sankey`       | `nodes:[{id,label}], links:[{source,target,value}]` | Flow diagram. |
| `treemap`      | `root:{name,children?,value?}` | Hierarchical size. |
| `heatmap`      | `xLabels:[], yLabels:[], cells:[{x,y,v}], colorScale:"sequential\|diverging"` | Accessible HTML-table heatmap (header `scope`, per-cell tooltip) that scales with text; same D3 color scale. |
| `mermaid`      | `diagram: string` | Client-side `mermaid.render`. The `diagram` is structurally linted at validate time (see [mermaid lint and verify_mermaid.py](#mermaid-lint-and-verify_mermaidpy)). |
| `image`        | `src: string` (`data:image/…;base64,…` or relative `assets/…`), `alt: string`, `title?` | Constrained `<img>`. Used for the Overview infographic. |
| `diff-view`    | `perspectives:[{slug,title,lead,items:[{before,after}]}]` | Grouped before/after table; each perspective is a header band plus one row per `{before,after}` item, word-diffed inline via jsdiff with a plain-text fallback. |

An unrecognized `type` renders a visible "unsupported section type `X`
(fragment `id`)" placeholder. It never fails the build — the contract is
forward-compatible by design.

A section MAY carry `"status"` (`ok|info|warn|error`) — a status icon
prepends to the section heading; a section with neither `title` nor `status`
is headerless. A section MAY carry `"help"` (string) — it becomes the section
heading's tooltip and a note on `help.html`; a non-empty fragment `"help"`
markdown or any section `help` shows a `❓` header link to that page. Both are
optional and back-compatible; an invalid `status` value or non-string `help`
fails validation.

`view` (`"release"|"production"`, absent ⇒ `"release"`) decides which of the
two permanent columns a section lands in; an invalid value fails validation. A
section MAY also carry `"menu": "<label>"` (non-empty string, else validation
fails), the producer-declared top-menu group label (see
[Layout, navigation, and split-screen model](#layout-navigation-and-split-screen-model)),
and `"module": "<id>"` (non-empty string), an opaque
module tag driving the global module filter (see
[Module filter](#module-filter)). `files:[{path,lang,excerpt,startLine?}]`
carries producer-embedded source excerpts; a path string matching a
`files[].path` on the same section becomes a clickable token opening a
preview modal (markdown via marked+DOMPurify, otherwise an escaped `<pre>`).
The build never reads files.

## diff-view body type

`diff-view` carries a grouped before/after synthesis. `perspectives` is a
non-empty list; each perspective is `{ slug, title, lead, items }` where
`slug` matches `[a-z0-9-]+`, `title` and `lead` are non-empty strings, and
`items` is a non-empty list of `{ before, after }` string pairs. The pair is
the entire item model — there is no change-kind field. `before` empty ⇒ a NEW
row, `after` empty ⇒ a DELETED row, both set ⇒ an UPDATED row. An item with
both `before` and `after` empty fails validation, and an empty `items` list
fails validation: a perspective with no real items is dropped by the producer,
never emitted as an empty shell.

The renderer draws one `<table class="diff-view-table">`. Each perspective
contributes a spanning header row — `title` with the `lead` as a muted inline
note — followed by one `tr.diff-pair` per item carrying `data-before` /
`data-after`, a left `dv-before` cell and a right `dv-after` cell. When the
jsdiff library is loaded the cells show a word-level diff (removed words in
`<del>`, added words in `<ins>`); without it each cell shows its plain
`before`/`after` text. An entirely empty cell renders a muted em-dash. A row
is never blank in either mode. The diff fill runs after the rows attach and
re-runs on every fragment re-render (menu switch, module switch, two-column
relayout), so the pairs stay correct whenever the section is shown. The item's
internal before/after is the change's own before/after and is independent of
the framework `view` column tag.

jsdiff is loaded from a version-pinned, SRI-pinned CDN `<script>` in
`index.html` alongside the other libraries. If the script fails to load the
section degrades to plain `before`/`after` text — the data is still fully
readable.

## mermaid lint and verify_mermaid.py

A `mermaid` section's `diagram` is structurally linted by
`validate_fragments.py` at validate time. The lint is deterministic and
dependency-free: it requires a known diagram header (`flowchart`/`graph`,
`sequenceDiagram`, `classDiagram`, `stateDiagram(-v2)`, `erDiagram`,
`journey`, `gantt`, `pie`, `mindmap`, `timeline`, `C4Context`/`C4Container`/
`C4Component`), a direction token (`TD|TB|LR|RL|BT`) when the header is
`flowchart`/`graph`, balanced `[] () {}` and quotes, balanced `subgraph`/`end`,
no reserved word (`end`, `graph`, `subgraph`, `class`, `click`, `style`,
`linkStyle`) used as a bare node id, no stray ``` ``` ``` fences, and content
after the header. A diagram that fails the lint is a normal validation error,
so `dev-report-build` refuses to ship it instead of letting it render as a
blank panel in the browser. A fragment with no `mermaid` section is
unaffected.

`scripts/verify_mermaid.py` is the standalone shared tool behind the gate. It
exposes the same Layer-1 lint plus an optional Layer-2 true-parse via
mermaid-cli (`mmdc` on `PATH`, `npx @mermaid-js/mermaid-cli`, or the official
Docker image); a non-zero render is a hard failure with the captured stderr.
When no mmdc is resolvable Layer 2 is skipped and the Layer-1 result stands —
a missing renderer is never treated as a failure. It runs as
`verify_mermaid.py text -|<file>` to lint one diagram or
`verify_mermaid.py fragments <dir>` to lint every `mermaid` section across a
fragment directory. Exit codes: `0` clean, `1` bad args, `2` unparseable
input, `4` one or more diagrams failed. Layer 2 is opt-in via this CLI (a
producer self-test); the validate-time gate is Layer 1 only so no dependency
is required to validate.

## Module filter

A report MAY partition content by **module** — an opaque producer-defined id.
The framework never parses or resolves it (`root`, `core`,
`modules/payments` are strings; resolving them is a producer concern). Three
optional, backward-compatible surfaces carry ids:

- a `body[]` section's `"module": "<id>"` (non-empty string; an invalid type
  fails validation);
- a `table` column with `"type": "module"`, each cell an opaque module-id
  string (empty/absent ⇒ the row is module-agnostic);
- a top-level manifest `"modules": ["<id>", …]`, written verbatim by
  `dev-report-build --modules id1,id2,…` (the build never parses the ids).

The shell renders one global `Module:` dropdown beside the
show/hide-previous-releases control. Its options are `All` ∪
`manifest.modules` ∪ every section `module` value ∪ every `type:"module"`
cell value across all loaded fragments, ordered `All` first, then `root` (if
present), then the rest lexically. Selecting module *M* hides any section
whose `module` is set and ≠ *M* and, in tables with a `type:"module"`
column, rows whose module cell ≠ *M*; sections with no `module` and
empty-module rows always stay visible; `All` filters nothing. The selection
is persisted in the URL hash so deep links and back/forward keep it, and it
composes with the two-column view, the top menu, the
show/hide-previous split, and the table filter. When no module ids exist
anywhere the selector is not rendered, so reports that do not use modules are
visually unchanged.

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
    ├── help.html                       # consolidated report-help page
    ├── assets/
    │   ├── app.js                      # generic renderer (copied verbatim)
    │   └── app.css                     # chrome/layout/status colors
    └── data/
        ├── manifest.json               # nav tree + rollup + release identity
        └── <category>/<fragment-id>.json
```

`assets/app.js|app.css` are copied verbatim from the Skill's
`scripts/assets/` into every release so the folder opens with no dependency on
the repo. `help.html` is the same shell with a `dev-report-help/v1` JSON
island built from every fragment's `help` (top-level markdown) and section
`help` strings, embedded in both embed and `--no-embed` modes (it is small);
it has no entries when no fragment uses `help`. `data/*.json` is always
written (diffable in git, re-buildable) even when it is also inlined into
`index.html` (see below).

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
        "path": "data/dependencies/dependency-graph.json" } ] }
  ]
}
```

`modules` is the verbatim `--modules id1,id2,…` list, present only when the
flag was passed; it seeds the global module-filter options and is never
parsed by the build.

The shell reads `manifest.json` first, renders the nav, then loads each
fragment on demand. Categories with no fragments are omitted from the nav.

`reports/releases.json` (top-level, newest-first) drives prev/next navigation:

```json
{
  "schema": "dev-report-releases/v1",
  "releases": [
    { "id": "2026.05.0", "vcs_ref": "v2026.05.0", "git_sha": "9f3c1a7",
      "created_at": "2026-05-17T09:30:00Z", "label": "May 2026",
      "commit_count": 96, "path": "2026.05.0/" },
    { "id": "2026.04.0", "vcs_ref": "v2026.04.0", "git_sha": "1b2d4e8",
      "created_at": "2026-04-12T08:00:00Z", "label": "April 2026",
      "commit_count": 71, "path": "2026.04.0/" }
  ]
}
```

`dev-report-build` reads, upserts by `id`, and rewrites this file atomically on
every build, and embeds the resulting (post-upsert, newest-first) content into
every `index.html` data island under the key `releases.json` — in both embed
and `--no-embed` modes, since it is tiny.

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

`dev-report-build` inlines the post-upsert `releases.json`, the manifest, and
every fragment into `index.html` as one
`<script id="report-data" type="application/json">…</script>` data island.
The island keys are `releases.json`, `data/manifest.json`, and
`data/<category>/<id>.json`. The loader's accessor is:

```
getData(path):
  if window.__REPORT_DATA__[path] exists → return it      (embedded; file:// safe)
  else if location.protocol === "file:" → reject          (no CORS fetch attempt)
  else → fetch(path)                                       (served mode)
```

`releases.json` is embedded under its own key in both embed and `--no-embed`
modes (it is tiny); the standalone `reports/releases.json` is also written for
git-diffability, served-mode use, and re-builds. The release-list loader reads
the embedded `releases.json` first and on a `file://` page never issues the
parent-relative `fetch('../releases.json')` (the opaque origin makes it a CORS
failure); served reports fetch the live file as the fallback. Default builds
also embed the manifest and every fragment so the folder works by double-click
with zero server and zero CORS; `data/*.json` is still written. `--no-embed`
skips inlining the manifest and fragments for very large reports meant to be
served (but still embeds `releases.json`); in that mode the folder is viewed
with a static server, e.g.:

```
python3 -m http.server --directory reports/2026.05.0
```

The previous-release split-screen loads sibling releases'
`../<prev>/data/<category>/<id>.json` — inherently a cross-origin read on
`file://`. There the pane shows an inline "needs the report served" message;
the current release still renders fully. Served reports load the sibling
fragments normally.

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

## Layout, navigation, and split-screen model

- **Shell title** is "Release candidate report". The rendered report title is
  `YYYY-MM-DD · <release-id>` — the date is the `release.created_at` date and
  `<release-id>` is the release id (the version). When `commit_count` (from
  `--commits`) is set, `N commits` renders on a second muted line; without it
  there is no commit line. vcs-ref, label, and SHA remain in the manifest but
  are not the displayed title. A status badge follows the title only when the
  shown release is stale: `⚠ superseded — latest is <newest-id>` (warn-amber)
  when the shown release id is not `releases[0].id` (newest by `created_at`),
  computed from the embedded `releases.json`. The newest release shows no
  badge — the absence is the "latest" signal; there is no `✓ latest` chip.
  The roll-up indicators are icon-prefixed status counts (`✅ 12`, `⚠️ 4`),
  not colored chips.
- **Permanent two columns.** Every fragment renders as two fixed side-by-side
  columns. The left **This release** column is the state *after* this release
  (all `view:"release"`/untagged sections, in `body[]` order). The right
  **vs production** column is the difference this release makes to production —
  the release-candidate's diff against the production branch, conceptually the
  `production..main` scope (all `view:"production"` sections, in order). An
  empty left column shows a muted `— nothing for this view —`; an empty right
  column shows that same string only when a production baseline exists,
  otherwise `No previous production to compare with`. The baseline signal is
  the embedded `releases.json` (a baseline exists iff some entry's `id`
  differs from the shown release's id — a build-time snapshot, no network read
  under `file://`); the renderer owns this message, producers never emit a
  placeholder. This is structural
  and explicitly distinct from the show/hide-previous-releases feature, which
  is an unrelated cross-release history view (the second pane loading the same
  fragment `id` from a sibling release via `releases.json`); it is **not** a
  comparison against the previous report or release. Untagged fragments are
  backward-compatible (everything lands left).
- **Left nav** is built from `manifest.json`, grouped by **area**: a status
  dot per fragment and one area head per group with a combined fragment count
  and worst member status. `test-coverage` and `test-reports` collapse into
  one `Tests` area; every other category is its own area. Each fragment link
  still routes by its real `category`/`id` (routing, deep links, and the
  previous-release pane are unchanged). An `overview` category is pinned
  first, a `report` category second, the rest lexical; the overview fragment
  (lexically-first `id` if several) is the default page on load. The URL hash
  (`#dependencies/dependency-graph`) deep-links and drives the back button.
- **Top menu (producer-declared, current report part only).** The in-content
  top menu is computed from the currently-displayed fragment: the distinct
  section `menu` labels in first-appearance order across its `body[]`, with a
  leading default item (the fragment's `title`, or `Overview`) collecting any
  sections that carry no `menu`. Selecting an item shows only that group's
  sections; the first is selected by default and the choice is persisted in
  the URL hash alongside the area/part/module state, so deep links and
  back/forward restore it (an absent/invalid value falls back to the first
  item). Switching the left-nav report part recomputes the menu from the
  newly shown fragment. A fragment with no `menu` labels renders no top menu
  and shows every section (backward-compatible). The menu is intra-part
  section-group navigation only — it never lists categories, tools, or
  sibling fragments; the left nav stays the area → report-part selector.
- A **show/hide-previous-releases toggle** (labelled "Show/hide previous
  releases") switches between current-release-only and a second pane showing
  the same fragment `id` from a sibling release.
- With the previous pane shown it has `◀ ▶` controls (and left/right arrow
  keys when the report has focus) that walk `releases.json`; entries after the
  current one are older. The pane loads
  `../<prev-release>/data/<category>/<fragment-id>.json` — a sibling-folder
  relative path that works when the report is served. On a `file://` page the
  pane shows an inline "Previous-release comparison needs the report served
  (e.g. `python3 -m http.server`)" message instead of a CORS error; the
  current release renders fully regardless.
- If a fragment `id` is absent in the previous release, the pane shows a
  "not present in `<release>`" placeholder (a newly added analyzer is handled
  gracefully).
- When both panes show the same fragment, a Δ table is computed from shared
  `metrics{}` keys (value, value, delta, %), and `metric-cards` with a
  `delta_metric` show an inline ▲/▼.
- **File preview.** A `table` `type:"file"` cell whose value matches a
  `files[].path` on the same section is a clickable token; it opens a modal
  rendering the producer-embedded excerpt (markdown sanitized via
  marked+DOMPurify, otherwise an escaped monospace `<pre>` with the lang and
  optional start-line label). "Open full file" is active only when served;
  inert under `file://`.
- **Section status icon.** A section's optional `status` (`ok|info|warn|
  error`) prepends `✅`/`ℹ️`/`⚠️`/`🚨` to its heading; a section with neither
  `title` nor `status` is headerless.
- **Consolidated help.** A non-empty fragment `help` (markdown) or any
  section `help` (string) adds a `❓` header link to `help.html` at the report
  root — one page listing every fragment's help and its sections' notes,
  built from an embedded JSON island (no `fetch`, `file://`-safe). A section's
  `help` is also its heading's hover tooltip.
- **Provenance panel.** A `🪜` header toggle reveals a panel with the
  producer's Skill, Tool, Version, the `YYYY-MM-DD HH:MM UTC` Generated
  timestamp, and a `skills/<skill>/` source path. The fragment footer renders
  the same timestamp through the shared formatter.
- **Graph pan/zoom.** Every `d3-graph` layout pans (drag) and zooms (scroll);
  a `Reset view` button restores the viewport.

`app.js` is a single hand-written classic script — no bundler, no npm. The
renderer is a `switch(section.type)` dispatch table.

## dev-report-build

```
dev-report-build <release-id> <fragments-dir> <reports-root> [--vcs-ref REF] [--label TEXT] [--commits N] [--modules id1,id2,...] [--no-embed] [--design FILE]
```

| Arg              | Meaning |
| ---------------- | ------- |
| `<release-id>`   | Explicit id, validated `[A-Za-z0-9._-]+`. Becomes the folder name. |
| `<fragments-dir>`| Staging dir of `*.json` fragments. The script reads each fragment's `category` and lays it out under `data/<category>/`. |
| `<reports-root>` | The `reports/` dir to write into and update. |
| `--vcs-ref`      | Optional tag/branch recorded in the manifests. |
| `--label`        | Optional human label; defaults to `<release-id>`. Recorded, but not the rendered title. |
| `--commits N`    | Optional integer commit count recorded as `commit_count` in the manifest and `releases.json`; the renderer formats the title `YYYY-MM-DD · <release-id> · N commits`. Omitted ⇒ `commit_count: null` and the `· N commits` clause is dropped. |
| `--modules LIST` | Optional comma-separated opaque module ids written verbatim into the manifest as top-level `modules`; seeds the global module filter. Ids are never parsed or resolved. Omitted ⇒ no `modules` key. |
| `--no-embed`     | Skip inlining the manifest and fragments into `index.html` (served mode, large reports). `releases.json` is still embedded under its own data-island key. |
| `--design FILE`  | Optional retheme. Extracts every CSS `:root{…}` block from `FILE` (fenced ` ```css ` or raw), concatenates them, and injects one `<style id="design-override">` immediately before `</head>` and after the app.css `<link>`, so the cascade overrides the theme variables. Works with and without `--no-embed`. A file with no `:root` block prints a non-fatal stderr notice and the default theme is used; it adds no exit code. |

Behavior: validate every fragment (same logic as `validate_fragments.py`);
build into a temp dir and move into place only on success (atomic); auto-capture
short SHA (best-effort — warn, do not fail, if not a git repo) and UTC
timestamp; lay fragments out by `category`; compute `rollup`; write
`manifest.json`; copy `assets/*`; embed `releases.json` into the data island
always and the manifest plus fragments unless `--no-embed`; write `help.html`
with a `dev-report-help/v1` island built from fragment/section `help` (always
embedded); inject the design override when `--design` resolves a `:root`
block; upsert the release into `releases.json` and rewrite atomically. Python 3, standard library only.
No LLM: `--design` only greps `:root{…}` blocks. Deriving a theme from a prose
`DESIGN.md` is the Skill's `references/design-to-theme.md` role; only these
`:root` vars are overridable (defined in `assets/app.css`): `--bg`, `--panel`,
`--panel-2`, `--border`, `--text`, `--muted`, `--accent`, `--ok`, `--info`,
`--warn`, `--error`.

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
"validate → fix → repeat" without invoking a full build. It imports the
Layer-1 mermaid lint from `scripts/verify_mermaid.py` so every `mermaid`
section's `diagram` is structurally checked as part of the same pass (see
[mermaid lint and verify_mermaid.py](#mermaid-lint-and-verify_mermaidpy)).
Python 3, standard library only.
