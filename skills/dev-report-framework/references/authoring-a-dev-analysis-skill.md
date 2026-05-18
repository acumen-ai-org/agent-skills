# Authoring a producer that emits conformant fragments

Every `dev-analysis-*` and `dev-test-*` Skill links its `to-fragment.py`
authors here. A producer emits report fragments and knows nothing about HTML,
JS, or D3 — the only coupling is the JSON contract in
[fragment-schema.md](fragment-schema.md). Get the JSON right and the framework
renders it generically; no framework change is ever needed for a new producer.

## Contents

- [The producer contract](#the-producer-contract)
- [Script vs synthesis split](#script-vs-synthesis-split)
- [Choosing status and severity](#choosing-status-and-severity)
- [Designing metrics for the diff](#designing-metrics-for-the-diff)
- [view — which column](#view--which-column)
- [Picking section types](#picking-section-types)
- [Behavior-shape before/after pair](#behavior-shape-beforeafter-pair)
- [The feedback loop](#the-feedback-loop)
- [Worked minimal producer](#worked-minimal-producer)
- [Menu groups (optional)](#menu-groups-optional)
- [Module attribution (optional)](#module-attribution-optional)
- [Out of scope](#out-of-scope)

## The producer contract

A producer Skill's `scripts/to-fragment.py` writes one or more `*.json` files
into a staging dir. Each file:

- conforms to [fragment-schema.md](fragment-schema.md) (validated, not assumed);
- has an `id` matching `[a-z0-9-]+`, unique within the release, **stable
  across releases** — the `id` is the cross-release diff key, so renaming it
  breaks the split-screen comparison and the prev/next walk;
- carries one `category` from the fixed enum (drives left-nav grouping);
- fills `producer{ skill, tool, version }` for the fragment footer.

The framework lays the file out at `data/<category>/<id>.json` and embeds it
into `index.html`. The producer never writes the manifest or `releases.json`.

## Script vs synthesis split

Two distinct authors touch a fragment:

1. **The script** (`to-fragment.py`, stdlib only, no LLM) writes the
   **factual** parts: `metrics{}` and factual `body[]` (tables, graphs,
   key-value extracted from tool output). It sets a provisional `status` from
   thresholds and a placeholder `summary`.
2. **The Skill's `*-synthesis.md` role** enriches `summary` to one plain-text
   line and appends narrative `body[]` (a `markdown` section interpreting the
   facts). It may raise `status` but should not invent metrics.

The merged object is what `validate_fragments.py` and `dev-report-build` check.
Keep the script deterministic; keep judgment in the role.

## Choosing status and severity

`status` drives the badge and the category roll-up. Use the same mapping
across producers so the report is comparable:

| `status` | Meaning |
| -------- | ------- |
| `ok`     | Analysis ran, nothing to flag. |
| `info`   | Ran, informational only (no action implied). |
| `warn`   | Ran, found something worth a look, non-blocking. |
| `error`  | Ran, found a blocking condition (the analysis succeeded — the *finding* is bad, not the run). |

A runner that itself broke is an exit code, not `status` — the fragment is
only written when the analysis completed. `severity` (0–100) optionally
fine-orders many `warn`/`error` fragments; omit it if there is nothing to
order.

## Designing metrics for the diff

`metrics{}` is the only thing the split-screen diffs. Design keys so a
release-over-release delta is meaningful:

- **Stable key names.** `cycle_count` in every release, not `cycles_v2`.
- **Monotonic meaning.** A key should mean the same thing each release so
  `current − previous` is interpretable.
- **Numbers only**, flat map. No nested objects, no strings, no units in the
  value (`92`, not `"92s"`). Put the unit on the matching `metric-cards` card.
- **Pair a card with its metric.** A `metric-cards` card with
  `delta_metric:"cycle_count"` shows ▲/▼ automatically in split mode.

## view — which column

Binding rule for setting a section's `"view"`:

- A section describing the **current post-release state** (the state after
  this release) ⇒ `"view":"release"` (or omit it — `release` is the default).
- A section describing the **delta against production** (what this release
  changes versus the production branch) ⇒ `"view":"production"`.
- A fact that is inherently both ⇒ emit **two sections**, one per view, each
  carrying only its half.

Set `view` deterministically in the script wherever the column is known from
the data; do not guess. A producer **never** emits an empty-column
placeholder — when a fragment has no `production`-view section the renderer
and the vs-production logic own the empty-column message
(`— nothing for this view —`, or `No previous production to compare with`
when there is no production baseline). Your job is only to tag the sections
you do emit.

## Picking section types

Map facts to the closest of the nine types
([section-types.md](section-types.md)):

- counts/measures a reader scans first → `metric-cards`;
- tabular findings → `table` (set `filterable` for long lists);
- a graph of relationships → `d3-graph` (`dag` for layered, `force`
  otherwise) — for a large graph aggregate to **module granularity**; the
  renderer pans/zooms but a module-level graph is the readable default;
- volume flowing between stages → `sankey`;
- size/share of a whole → `treemap`;
- a label×label matrix → `heatmap`;
- short labeled facts → `key-value`;
- authored (not data-derived) diagrams → `mermaid`;
- narrative interpretation → `markdown` (the synthesis role's output).

Order `body[]` for a reader: cards first, then detail, narrative last. Unknown
types are tolerated but never emit one deliberately — it ships a placeholder.

## Behavior-shape before/after pair

To make an architectural, security, or schema shift legible, emit a
`mermaid view:"production"` (prior shape) paired with a `mermaid view:"release"`
(new shape) under the **same** `menu` label, at the same abstraction level —
the framework's two-column layout renders them side by side with no contract
or renderer change. Full authoring rules (same diagram type/granularity,
behavior not raw diff, single-`release` diagram when there is no honest
"before", mandatory `verify_mermaid.py` pass) are in
[before-after-mermaid.md](before-after-mermaid.md).

## The feedback loop

Run the validator after every change to `to-fragment.py`, before any build:

```
python3 .../validate_fragments.py <staging-dir>
```

Exit `0` means every fragment conforms — proceed to `dev-report-build`. Exit
`3` prints a per-file error list on stderr; fix and re-run. Iterate
validate → fix → repeat without paying for a full build. `dev-report-build`
runs the identical check internally and writes nothing on failure, so a build
can never produce a partially-valid report.

## Worked minimal producer

The smallest conformant fragment a `to-fragment.py` can emit:

```json
{
  "schema": "dev-report-fragment/v1",
  "id": "license-summary",
  "category": "dependencies",
  "title": "License summary",
  "summary": "All 312 dependencies use OSI-approved licenses.",
  "status": "ok",
  "producer": { "skill": "dev-analysis-dependencies", "tool": "syft", "version": "1.0.0" },
  "generated_at": "2026-05-17T09:30:00Z",
  "metrics": { "packages": 312, "copyleft": 0 },
  "body": [
    { "type": "metric-cards", "cards": [
      { "label": "Packages", "value": 312, "delta_metric": "packages" },
      { "label": "Copyleft", "value": 0, "delta_metric": "copyleft" } ] },
    { "type": "markdown", "md": "No copyleft obligations introduced this release." }
  ]
}
```

This validates, renders four ways (two cards + prose), and diffs both metrics
against the previous release.

## Menu groups (optional)

Set `"menu": "<label>"` on `body[]` sections to give your report part a top
menu. The renderer lists the distinct labels (first-appearance order); any
untagged sections collect under a leading default item named after the
fragment's `title`. Absent on every section ⇒ no top menu and all sections
show (legacy). The menu is scoped to your report part only — switching the
left-nav part recomputes it from that fragment; it never lists sibling
fragments or tools. Use it to break a long report part into reader-chosen
groups (e.g. `Graph`, `Cycles`, `ADR`); leave it off for a single-flow part.

## Module attribution (optional)

A repo's `dev-process.json` may define `modules` (folder patterns). The report
shell shows a global `Module:` filter; opt in so it narrows your fragment:

- Tag a whole section with `"module": "<id>"`, or give a `table` a column with
  `"type": "module"` whose cells are module ids.
- Untagged sections and empty module cells are never filtered (module-agnostic
  content always shows). Opting in is optional — a fragment that tags nothing
  simply isn't module-filterable.

**Binding:** a module-aware producer **always** resolves a repo-relative path
to a module id through the shared resolver — `python3
"${CLAUDE_PLUGIN_ROOT}/scripts/modules.py" id <path> --config
<repo>/dev-process.json` — and **never** hand-tags or parses ids itself.
Resolve every path the same way so one repo's module taxonomy is consistent
across every producer. With no config or an empty `modules` the resolver
returns `root` for everything; emitting `root` everywhere is the **only**
acceptable no-modules state (the selector then hides itself). Never invent an
id, never special-case a path, never fall back to a literal string.

## Out of scope

Anything about rendering, HTML, or D3 (the framework owns it). Writing the
manifest or `releases.json` (`dev-report-build` derives them). Choosing a
release id (a caller-supplied CLI arg, see the Skill's inputs). Resolving
module ids yourself (always shell out to `scripts/modules.py`).
