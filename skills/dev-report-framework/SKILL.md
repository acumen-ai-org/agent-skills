---
name: dev-report-framework
description: Aggregates report fragments emitted by dev-analysis-* and dev-test-* Skills into one standalone, navigable HTML release-candidate report folder per release, with a permanent two-column This-release/Δ-vs-previous layout and a show/hide-previous-releases split-screen. Validates fragments against the dev-report-fragment/v1 contract, lays them out by category, embeds everything into index.html so the folder opens via file:// with no server, and upserts a top-level releases.json for prev/next navigation. Use when building or refreshing a release report from collected analysis fragments, or when authoring a producer Skill that must emit conformant fragment JSON.
---

# dev-report-framework

The seam every `dev-analysis-*`/`dev-test-*` Skill targets. Producers emit
JSON fragments; this Skill validates them and builds a self-contained report
folder. The renderer dispatches generically on `body[].type`, so a new
producer needs zero framework changes.

The contract is the only coupling. It lives in
[`references/fragment-schema.md`](references/fragment-schema.md) and ships with
the Skill. The scripts are run, not read:
[`scripts/validate_fragments.py`](scripts/validate_fragments.py) and
[`scripts/dev-report-build`](scripts/dev-report-build).

## Contents

- [Inputs](#inputs)
- [The fragment contract at a glance](#the-fragment-contract-at-a-glance)
- [Layout and UI](#layout-and-ui)
- [Module filter](#module-filter)
- [Procedure](#procedure)
- [Apply design](#apply-design)
- [Standalone viewing and the file:// caveat](#standalone-viewing-and-the-file-caveat)
- [Authoring a producer](#authoring-a-producer)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

`dev-report-build` is positional-first; only the I/O is positional, the rest
are flags.

| Input            | Required | Notes |
| ---------------- | -------- | ----- |
| `<release-id>`   | yes      | Explicit id, validated `[A-Za-z0-9._-]+`. Becomes the folder name and the diff/nav key. |
| `<fragments-dir>`| yes      | Staging dir of `*.json` fragments. Each fragment's `category` decides its `data/<category>/` slot. |
| `<reports-root>` | yes      | The `reports/` dir to create/update. |
| `--vcs-ref REF`  | no       | Tag/branch recorded in the manifests; `null` if omitted. |
| `--label TEXT`   | no       | Human label; defaults to `<release-id>`. Recorded but not the displayed title (see [Layout and UI](#layout-and-ui)). |
| `--commits N`    | no       | Records `commit_count` in the manifest; the renderer formats the title as `YYYY-MM-DD · <release-id> · N commits`. Omitted ⇒ the `· N commits` clause is dropped. |
| `--modules LIST` | no       | Comma-separated opaque module ids written verbatim into the manifest as `modules`; seeds the global module filter (see [Layout and UI](#layout-and-ui)). Omitted ⇒ no `modules` key. |
| `--no-embed`     | no       | Skip inlining data into `index.html` (served mode, very large reports). |
| `--design FILE`  | no       | Retheme: extract every CSS `:root{...}` block from `FILE` and inject it as `<style id="design-override">` after the app.css link. No `:root` block → non-fatal stderr notice, default theme, exit 0. See [Apply design](#apply-design). |

The build auto-captures `git rev-parse --short HEAD` (best-effort — a stderr
warning and `git_sha:null` if not a git repo, never a failure) and a UTC
timestamp. Requirements: `python3` (standard library only — no pip packages),
`git` (optional, only for the SHA). Viewing needs a browser; CDN libraries
load from the network on first open (cached after).

## The fragment contract at a glance

One JSON object per fragment. Required: `schema`
(`"dev-report-fragment/v1"`), `id` (`[a-z0-9-]+`), `category` (fixed enum:
`architecture | evolution | dependencies | quality | security | schema |
contracts | mission | test-coverage | test-reports | overview`), `title`,
`summary`, `status` (`ok|info|warn|error`), `producer`, `generated_at`,
`body[]`. Optional: `severity` (0–100), `metrics{}` (flat `string→number`, the
diff surface). Each `body[]` element is one of ten typed sections (`markdown`,
`table`, `key-value`, `metric-cards`, `d3-graph`, `sankey`, `treemap`,
`heatmap`, `mermaid`, `image`); an unknown type renders a visible placeholder,
never a failure. A section MAY also carry `view` (`"release"|"delta"`,
absent ⇒ `"release"`), `module` (an opaque module-id tag), and `files[]`
(producer-embedded excerpts opened in a preview modal). A `table` row MAY
carry `children[]` (expandable subrows) and a `table` column MAY be
`type:"file"` or `type:"module"`.

Full rules and one filled example per type:
[`references/fragment-schema.md`](references/fragment-schema.md). Rendered
behavior per type: [`references/section-types.md`](references/section-types.md).
`fragment-schema.md` is the single source of truth.

## Layout and UI

The shell is titled **Release candidate report**.

- **Title.** The displayed report title is
  `YYYY-MM-DD · <release-id> · N commits`, where the date is the
  `release.created_at` date, `<release-id>` is the release id (the version),
  and `N` is `--commits`. Without `--commits` it is
  `YYYY-MM-DD · <release-id>`. The vcs-ref, label, and SHA stay in the
  manifest but are not the rendered title. A status badge follows the title,
  read from the embedded `releases.json`: `✓ latest` (ok-green) when the
  shown release is `releases.json[0]` (newest by `created_at`), otherwise
  `⚠ superseded — latest is <newest-id>` (warn-amber) so a stale report file
  is obvious. The badge text carries the state (not color alone).
- **Two columns, always.** Every fragment renders as two fixed side-by-side
  columns: left **This release** (all `view:"release"`/untagged sections in
  order), right **Δ vs previous** (all `view:"delta"` sections in order). An
  empty column shows `— nothing for this view —`. This is permanent and
  distinct from the previous-releases toggle.
- **Show/hide previous releases.** The sidebar button (labelled
  `Show/hide previous releases`) toggles the second pane that loads the same
  fragment `id` from a sibling release, with the metric Δ table and `◀ ▶`
  release walk. Loading a sibling release's fragment needs the report served
  (`python3 -m http.server`); on a `file://` page that pane shows an inline
  "needs the report served" message and the current release still renders
  fully.
- **Overview landing.** A `category:"overview"` fragment is pinned first in
  the left nav and is the default page on load (lexically-first `id` if
  several). It renders like any fragment.
- **Per-section top menu.** Selecting a category with more than one fragment
  shows a horizontal tab menu of that category's fragments inside the content
  area; picking one shows just that fragment. The left nav still lists
  categories → fragments.
- **File preview.** A path token (a `table` `type:"file"` cell matching a
  `files[].path`) opens a modal rendering the producer-embedded excerpt —
  markdown via marked+DOMPurify, otherwise an escaped `<pre>`. "Open full
  file" is inert under `file://`.
- **Retheming.** `--design` is unchanged (see [Apply design](#apply-design)).

## Module filter

A report MAY partition content by **module**, an opaque producer-defined id
the framework never parses or resolves. Three optional, backward-compatible
surfaces carry ids: a `body[]` section's `"module": "<id>"`, a `table`
`type:"module"` column's cell values, and the manifest `modules` list
(`dev-report-build --modules id1,id2,…`, written verbatim).

The shell renders one global `Module:` dropdown next to the
show/hide-previous-releases control. Options are `All` ∪ `manifest.modules`
∪ every section `module` value ∪ every `type:"module"` cell value across all
loaded fragments, ordered `All`, then `root` (if present), then the rest
lexically. Selecting module *M* hides any section whose `module` is set and
≠ *M*, and in any table with a `type:"module"` column hides rows whose module
cell ≠ *M*; sections with no `module` and rows with an empty/absent module
cell always stay visible. `All` filters nothing. The selection rides in the
URL hash (so deep links and back/forward keep it) and composes with the
two-column view, the per-section menu, the show/hide-previous split, and the
table filter. **Inert when absent:** if no module ids exist anywhere the
selector is not rendered, so reports that do not use modules look unchanged.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Collect   — gather producer *.json into one staging dir
- [ ] 2. Validate  — validate_fragments.py <staging>  → must exit 0
- [ ] 3. Build     — dev-report-build <id> <staging> <reports-root>
- [ ] 4. Verify    — open index.html, check nav + a body type + split mode
```

### 1. Collect

Put every fragment a producer emitted into one staging dir (flat, `*.json`).
The build reads each fragment's `category` and lays it out under
`data/<category>/`; you do not pre-create the category folders.

### 2. Validate

```bash
python3 "scripts/validate_fragments.py" <staging-dir>
```

Exit `0` → every fragment conforms, proceed. Exit `3` → a per-file error list
prints on stderr; fix the producer, re-run. This is the fast feedback loop —
iterate validate → fix → repeat without a full build. `dev-report-build` runs
the identical check internally, so step 3 cannot produce a partial report.

### 3. Build

```bash
python3 "scripts/dev-report-build" \
  <release-id> <staging-dir> <reports-root> \
  [--vcs-ref REF] [--label TEXT] [--commits N] [--modules LIST] [--no-embed]
```

The build validates again, lays fragments out by `category`, computes the
roll-up, writes `data/manifest.json` and every `data/<category>/<id>.json`,
copies `assets/*`, embeds the manifest + all fragments into `index.html`
unless `--no-embed`, and upserts `<release-id>` into
`reports/releases.json` (newest-first). It builds into a temp dir and moves
into place only on success — a failed build leaves `reports/` untouched. The
trailing `OK …` line confirms; a non-zero exit means nothing usable was
written (see [Exit codes](#exit-codes)).

### 4. Verify

Open `reports/<release-id>/index.html` (double-click). Confirm: the title
reads `YYYY-MM-DD · <release-id>[ · N commits]` followed by a
`✓ latest`/`⚠ superseded` badge; an `overview` fragment (if any) is
pinned first and shown on load; the left nav lists categories with status dots
and a per-category roll-up; every fragment shows the two **This release** /
**Δ vs previous** columns; a multi-fragment category shows the per-section top
menu; at least one non-trivial body type (graph/table/heatmap) draws. If a
second release exists, serve the report (`python3 -m http.server`), toggle
**Show/hide previous releases**, and confirm the right pane loads the
previous release and the metric Δ table appears; on a `file://` page that
pane shows the "needs the report served" message instead.

## Apply design

Optional. Run only when a caller wants the report rethemed to a brand —
`reports.designDoc` points at a `DESIGN.md`. The default dark theme is used
otherwise; this step is skippable with no effect on the contract.

1. **Ensure a CSS theme exists.** If `reports.designDoc` already contains a
   fenced ` ```css ` block with a `:root { … }` rule, use the file as-is.
   Otherwise run [`references/design-to-theme.md`](references/design-to-theme.md)
   on the doc — it emits exactly one fenced ` ```css ` `:root{}` block — and
   save that output to a file.
2. **Build with it.**

   ```bash
   python3 "scripts/dev-report-build" \
     <release-id> <staging-dir> <reports-root> --design <css-file>
   ```

`--design` extracts every `:root{…}` block from the file (fenced or raw),
concatenates them, and injects one `<style id="design-override">…</style>`
immediately before `</head>`, after the app.css `<link>`, so the cascade
overrides the theme. Works identically with and without `--no-embed`. If the
file has **no** `:root` block the build prints a non-fatal stderr notice,
uses the default theme, and still exits `0` — `--design` adds no exit code.

Only these `:root` custom properties are overridable (defined in
`assets/app.css`): `--bg`, `--panel`, `--panel-2`, `--border`, `--text`,
`--muted`, `--accent`, `--ok`, `--info`, `--warn`, `--error`. Layout, spacing,
and fonts are the framework's and are not themeable.

## Standalone viewing and the file:// caveat

Every build embeds the post-upsert `releases.json` into `index.html`'s
`<script id="report-data" type="application/json">` data island under the key
`releases.json`. Default builds additionally embed the manifest and every
fragment (keys `data/manifest.json` and `data/<category>/<id>.json`). The
loader reads `window.__REPORT_DATA__[path]` first. On a `file://` page it
never issues a network `fetch` (the opaque origin makes
`fetch('data/manifest.json')` or `fetch('../releases.json')` a CORS failure
in Chromium and inconsistent in Safari); it uses the embedded copy and
degrades silently if one is absent — no thrown CORS error. When served
(http/https) the `fetch` is the fallback. `data/*.json` and the standalone
`reports/releases.json` are still written (git-diffable, re-buildable, served
mode). Because each report embeds its own build-time `releases.json`
snapshot, the title's latest/superseded badge reflects what was known at
build time on `file://`; a served report re-reads the live
`reports/releases.json`.

`--no-embed` is for very large reports meant to be served; it still embeds
`releases.json` (it is tiny) but not the manifest or fragments. View with a
static server:

```bash
python3 -m http.server --directory reports/<release-id>
```

CDN libraries (marked, DOMPurify, D3 v7, d3-sankey, mermaid) load from the
network on first open and are pinned with SRI hashes in `index.html`; the
browser caches them afterward. Vendoring them into `assets/` is a future
option, not part of v1.

## Authoring a producer

If you are writing a `dev-analysis-*`/`dev-test-*` Skill that must emit
fragments, follow
[`references/authoring-a-dev-analysis-skill.md`](references/authoring-a-dev-analysis-skill.md):
the script writes factual `metrics{}` + `body[]`, the Skill's
`*-synthesis.md` role enriches `summary` and adds narrative, the merged JSON
is validated with `validate_fragments.py` before handoff. Keep `id` stable
across releases — it is the cross-release diff key.

## Outputs

```
reports/
├── releases.json                 # newest-first; upserted by id; also embedded
└── <release-id>/
    ├── index.html                # shell; data island holds releases.json always,
    │                             #   manifest+fragments too unless --no-embed
    ├── assets/{app.js,app.css}   # copied verbatim from the Skill
    └── data/
        ├── manifest.json         # nav tree + rollup + release identity
        └── <category>/<id>.json  # one file per fragment, always written
```

Categories with no fragments are omitted from the nav. `assets/*` and the
shell are identical bytes per release so the folder is dependency-free.

## Failure modes

- **A fragment is invalid** → validate (or build) exits `3` with a per-file
  error list on stderr; the build writes nothing. Fix the producer, re-run.
- **`fragments-dir` has no `*.json`** → validation fails with a clear message;
  nothing is built.
- **Not a git repo / `git` missing** → stderr warning, `git_sha:null`, build
  still succeeds (provenance degrades, the report does not).
- **Empty report on double-click** → the build used `--no-embed`; either
  rebuild without it or serve the folder with `python3 -m http.server`.
- **Previous-release pane shows "needs the report served"** → expected on a
  `file://` page; a sibling release's fragment cannot be read across the
  opaque origin. Serve the report to compare releases. The current release
  renders fully regardless.
- **Title badge reads `⚠ superseded` after a newer release** → the file is a
  stale build-time snapshot; rebuild this release, or serve the report (the
  served loader reads the live `reports/releases.json`).
- **Visualizations blank, no network** → CDN libraries could not load on first
  open; reopen with network, then it is cached.
- **`reports-root` unwritable** → exit `2`, nothing moved into place (the
  temp-dir build is discarded).

## Exit codes

`dev-report-build`:

| Code | Meaning |
| ---- | ------- |
| `0`  | Report folder written; `releases.json` updated. |
| `1`  | Bad arguments / invalid `release-id`. |
| `2`  | I/O failure (unreadable `fragments-dir`, unwritable `reports-root`). |
| `3`  | One or more fragments failed contract validation — nothing written. |

`validate_fragments.py`:

| Code | Meaning |
| ---- | ------- |
| `0`  | Every fragment conforms. |
| `1`  | Bad arguments / usage. |
| `3`  | One or more fragments invalid — per-file errors on stderr. |
