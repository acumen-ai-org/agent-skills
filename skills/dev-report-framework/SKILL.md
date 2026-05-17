---
name: dev-report-framework
description: Aggregates report fragments emitted by dev-analysis-* and dev-test-* Skills into one standalone, navigable HTML report folder per release, with a this-release-vs-previous split-screen. Validates fragments against the dev-report-fragment/v1 contract, lays them out by category, embeds everything into index.html so the folder opens via file:// with no server, and upserts a top-level releases.json for prev/next navigation. Use when building or refreshing a release report from collected analysis fragments, or when authoring a producer Skill that must emit conformant fragment JSON.
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
- [Procedure](#procedure)
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
| `--label TEXT`   | no       | Human label; defaults to `<release-id>`. |
| `--no-embed`     | no       | Skip inlining data into `index.html` (served mode, very large reports). |

The build auto-captures `git rev-parse --short HEAD` (best-effort — a stderr
warning and `git_sha:null` if not a git repo, never a failure) and a UTC
timestamp. Requirements: `python3` (standard library only — no pip packages),
`git` (optional, only for the SHA). Viewing needs a browser; CDN libraries
load from the network on first open (cached after).

## The fragment contract at a glance

One JSON object per fragment. Required: `schema`
(`"dev-report-fragment/v1"`), `id` (`[a-z0-9-]+`), `category` (fixed enum),
`title`, `summary`, `status` (`ok|info|warn|error`), `producer`,
`generated_at`, `body[]`. Optional: `severity` (0–100), `metrics{}` (flat
`string→number`, the diff surface). Each `body[]` element is one of nine typed
sections (`markdown`, `table`, `key-value`, `metric-cards`, `d3-graph`,
`sankey`, `treemap`, `heatmap`, `mermaid`); an unknown type renders a visible
placeholder, never a failure.

Full rules and one filled example per type:
[`references/fragment-schema.md`](references/fragment-schema.md). Rendered
behavior per type: [`references/section-types.md`](references/section-types.md).

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
  [--vcs-ref REF] [--label TEXT] [--no-embed]
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

Open `reports/<release-id>/index.html` (double-click). Confirm: the left nav
lists categories with status dots and a per-category roll-up; clicking a
fragment renders it; at least one non-trivial body type (graph/table/heatmap)
draws. If a second release exists, toggle **Split view** and confirm the right
pane loads the previous release and the metric Δ table appears.

## Standalone viewing and the file:// caveat

Default builds **embed** the manifest and every fragment into `index.html` as
one `<script id="report-data" type="application/json">` data island. The
loader reads `window.__REPORT_DATA__[path]` first and only falls back to
`fetch`. This is why the folder opens by double-click with no server: a
`file://` origin is opaque and `fetch('data/manifest.json')` is blocked by
same-origin policy in Chromium and inconsistent in Safari — embedding
sidesteps CORS entirely. `data/*.json` is still written (git-diffable,
re-buildable).

`--no-embed` is for very large reports meant to be served. In that mode view
with a static server:

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
├── releases.json                 # newest-first; upserted by id
└── <release-id>/
    ├── index.html                # shell; data island filled unless --no-embed
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
