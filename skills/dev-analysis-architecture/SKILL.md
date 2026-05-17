---
name: dev-analysis-architecture
description: Analyzes whether a codebase's structure matches its intended architecture. Runs a per-stack analyzer (dependency-cruiser, madge, or Nx for TypeScript/JavaScript; ArchUnitNET/NetArchTest or MSADoc for .NET; cargo-modules for Rust; Structurizr DSL for any stack or F#), normalizes the module graph and any rule violations into one dev-report-fragment/v1 architecture fragment with a dependency graph, cycle list, and node/edge/cycle/depth metrics, then a synthesis role narrates the result. Use when assessing module boundaries, dependency cycles, layering violations, or architectural drift for a release report.
---

# dev-analysis-architecture

Answers "does the structure match the intent?" Each runner executes one
analyzer, writes `<id>.raw.<ext>`, and `to-fragment.py` normalizes that into a
single `architecture` fragment for [`dev-report-framework`](../dev-report-framework/SKILL.md).
The Skill is self-contained — roles live in `references/`, never as registered
subagents.

Two stages per analyzer, mirroring render→decode: `run-<tool>.sh` runs the
tool, then `to-fragment.py` emits the fragment. Scripts write only facts; the
[synthesis role](references/architecture-synthesis.md) adds the narrative.

## Contents

- [Inputs](#inputs)
- [Picking the analyzer](#picking-the-analyzer)
- [Procedure](#procedure)
- [Tool-free fallback](#tool-free-fallback)
- [Module dimension](#module-dimension)
- [The fragment it emits](#the-fragment-it-emits)
- [Authoring layering rules](#authoring-layering-rules)
- [F# limitation](#f-limitation)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

Every runner takes the same positional contract:

```
scripts/run-<tool>.sh   <target>  <out_dir>  [extra…]
```

| Input       | Required | Notes |
| ----------- | -------- | ----- |
| `<target>`  | yes      | The thing to analyze: a source dir (depcruise/madge), an Nx workspace, a `.dsl` file (Structurizr), a solution dir (MSADoc), an arch-test project dir (ArchUnitNET), a crate dir (cargo-modules). |
| `<out_dir>` | yes      | Where `<id>.raw.<ext>` and `<id>.fragment.json` land. Created if absent. |
| `[extra…]`  | no       | depcruise/madge take a source glob/entry (default `src`). |

Runtimes are detected, never installed. Node for depcruise/madge/nx, Docker
for Structurizr (pinned `structurizr/cli` and `structurizr/lite` images),
the .NET SDK for MSADoc/ArchUnitNET, cargo for cargo-modules. `python3`
(standard library only) for `to-fragment.py`. A missing runtime prints the
exact install line plus the pinned run line and exits `3`.

## Picking the analyzer

| Stack | Analyzer | Runner |
| ----- | -------- | ------ |
| TS/JS modules + boundary rules | dependency-cruiser | `run-depcruise.sh` |
| TS/JS circular deps (config-free) | madge | `run-madge.sh` |
| TS/JS Nx monorepo project graph | Nx Graph | `run-nx-graph.sh` |
| .NET layering rules as tests | ArchUnitNET / NetArchTest | `run-archunitnet.sh` |
| .NET service catalog/flow | MSADoc | `run-msadoc.sh` |
| Rust module graph | cargo-modules | `run-cargo-modules.sh` |
| Any stack / F# intended model | Structurizr DSL | `run-structurizr.sh` |

Run more than one when a repo is multi-stack; each emits its own fragment with
a distinct `id`.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Pick analyzer   — per the stack table
- [ ] 2. Run runner      — scripts/run-<tool>.sh <target> <out_dir>
- [ ] 2b. Tool-free path  — if EVERY runner you need exits 3, run the
                           tool-free fallback instead (see that section)
- [ ] 3. Synthesize      — references/architecture-synthesis.md on the fragment
- [ ] 4. Validate        — validate_fragments.py <out_dir>  → must exit 0
```

If no analyzer is installed, step 2b keeps the Skill producing a valid
fragment — it never fails solely because no analyzer is available.

### 1. Pick analyzer

Use the [stack table](#picking-the-analyzer). For F# components, go straight to
Structurizr (see [F# limitation](#f-limitation)).

### 2. Run the runner

```bash
bash "scripts/run-depcruise.sh" <target> <out_dir> [glob]
```

The trailing `TOOL <name> exit=<n>` line reports the result. Exit `0`/`4`
means the fragment was written (`4` = blocking violations found, a successful
analysis with a bad finding). Exit `3` means a runtime is missing — the script
already printed the exact install and pinned run lines; do not auto-install.
Exit `2` means the tool ran but its output was unparseable; the raw file is
kept for diagnosis. The same two-stage shape applies to every runner.

### 3. Synthesize

Follow [`references/architecture-synthesis.md`](references/architecture-synthesis.md)
with the written `<id>.fragment.json` as input. Run it inline, or — for fresh,
unbiased context — delegate it to an isolated agent passing the role file's
contents as instructions and the fragment as the task. Merge the role's
`summary`, narrative `markdown` body, and (only ever raised) `status` back into
the fragment.

### 4. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <out_dir>
```

Exit `0` → the fragment conforms, hand it to `dev-report-build`. Exit `3` →
fix and re-run. This is the feedback loop; iterate validate → fix → repeat.

## Tool-free fallback

When every analyzer runner you would use exits `3` (Node, Docker, the .NET
SDK, and cargo all absent — no runtime can be installed), the Skill still
produces a valid `architecture` fragment via a pure-`python3`-plus-`git` path.
It never fails solely because no analyzer is installed.

```
- [ ] a. Scan source   — python3 scripts/collect-structure.py <repo> <out_dir> [ref]
- [ ] b. Apply judgement — references/structure-from-source.md on the raw JSON
- [ ] c. Normalize     — python3 scripts/to-fragment.py architecture-source \
                          <out_dir>/architecture-source.raw.json \
                          <out_dir>/architecture-source.fragment.json
- [ ] d. Synthesize + validate — steps 3 and 4 above, unchanged
```

**a. Scan source.** `scripts/collect-structure.py <repo> <out_dir> [ref]`
statically scans tracked source for a module/package dependency inventory
across stacks (TS/JS `import`/`require`; Python `import`/`from`; C#/F# `using`
+ `.csproj`/`.fsproj` `<ProjectReference>`; Rust `mod`/`use`; Go `import`) —
nodes + directed edges with `value` = import/reference count — and an ADR
inventory. With `[ref]` every file is read from `git show <ref>:<path>` so a
release tag is inventoried without a checkout. Because this *is* the no-tool
path it never exits `3`: exit `0` on success, `5` on a bad repo/ref, `1` on
bad args. It writes one raw JSON, `architecture-source.raw.json`.

ADR inventory globs (matched against repo-relative paths):

```
docs/adr*/**/*.md   docs/adr*/*.md
docs/decisions/**/*.md   docs/decisions/*.md
adr/**/*.md   adr/*.md
**/*-adr-*.md
```

Each match contributes its path, `# ` title, and `Status:` line to the ADR
index.

**b. Apply judgement.** Module grouping and C4 boundaries are judgement the
script cannot make. Read [`references/structure-from-source.md`](references/structure-from-source.md)
against the raw JSON — inline, or delegated to an isolated agent for fresh
context — and write its strict payload next to the raw (it shares the raw's
`kind`/node/edge shape). Skip this only when no judgement is needed; the raw
alone is already a valid `to-fragment.py` input.

**c. Normalize.** Run `to-fragment.py` on the raw (or the role payload). The
tool-free path emits the same `architecture` fragment with the existing
metrics keys plus: a `d3-graph` (layout `force`/`dag`, or `chord` for
all-to-all coupling — chord is allowed by the framework), a `sankey` of
import flow weighted by import count, a C4 `mermaid` context/container view,
and an ADR `table` + a short `markdown` index.

**d.** Synthesize and validate exactly as steps 3 and 4 — the fragment is
identical in shape to a tool-produced one, so the rest of the pipeline is
unchanged.

Every `run-*.sh` wrapper is untouched: each still exits `3` (with its install
and pinned-run lines) when its runtime is absent. The fallback is selected by
this guidance when all of them do, not by rewriting any runner.

## Module dimension

The tool-free path's per-file listing table and ADR table each carry a
`type: "module"` column so the framework's global `Module:` selector can
filter their rows. The id for a row's path comes from the shared resolver —
`scripts/modules.py id <repo-relative-path> --config <repo>/dev-process.json`
— shelled out by `to-fragment.py`; the resolution rule is never reimplemented
here. `collect-structure.py` records the `<repo>/dev-process.json` location in
its raw so `to-fragment.py` can find the config.

With no `dev-process.json` or an empty `modules` array the resolver returns
`root` for every path, so the column is present but inert (every row stays
visible under any selection) — no special-casing.

The whole-repo structural views — the dependency `d3-graph`, the import-flow
`sankey`, and the C4 `mermaid` — are repo-wide by construction and stay
module-agnostic (no section `module`), so they always show regardless of the
selector.

## The fragment it emits

One fragment, `category: architecture`, `schema: dev-report-fragment/v1`.

- `metrics{ node_count, edge_count, cycle_count, max_depth }` — the
  cross-release diff surface. `max_depth` is the longest acyclic dependency
  path (cycle members are treated as depth 0 so a cycle does not make it
  infinite).
- `body[]` — a `metric-cards` row, the dependency graph as a `d3-graph`
  (`layout: dag`; cycle members in a distinct group), a `Cycles` table when
  cycles exist, a `Rule violations` table when the analyzer reported any. Above
  300 nodes the graph is replaced by a note (the metrics and tables stay
  authoritative) so the report stays renderable. The tool-free path adds a
  `sankey` of import flow (weighted by import count), a C4 `mermaid`, a
  per-file listing `table`, and an ADR `table` + `markdown` index, and may set
  the graph `layout` to `chord`. The listing and ADR tables carry a
  `type: "module"` column (see [Module dimension](#module-dimension)); the
  graph, sankey, and C4 stay module-agnostic.
- `status` — `ok` (clean), `warn` (cycles or advisory violations), `error`
  (a blocking layering violation; runner exits `4`).

The script writes the factual parts; the synthesis role enriches `summary` and
appends the narrative `markdown`. See
[`references/architecture-synthesis.md`](references/architecture-synthesis.md).

## Authoring layering rules

How to express "a lower layer must not depend on an upper layer" in each
analyzer's rule language, and how that violation reaches the fragment:
[`references/rule-authoring.md`](references/rule-authoring.md).

## F# limitation

ArchUnitNET/NetArchTest reflect over compiled CLR assemblies; this maps poorly
to idiomatic F# modules and functions, so F# layering rules are weak and must
not be relied on. F# architecture analysis falls back to a hand-authored
Structurizr DSL model run through `run-structurizr.sh`, not reflection rules.
State this in any report covering F#. Full detail:
[`references/rule-authoring.md`](references/rule-authoring.md#f-architecture-limitation).

## Outputs

In `<out_dir>`:

- `<id>.fragment.json` — the validated architecture fragment (hand to
  `dev-report-build`).
- `<id>.raw.<ext>` — the analyzer's raw output, kept for diagnosis.
- `<id>.stderr.log` / `<id>.stdout.log` — runner diagnostics.

`<id>` is per-tool and stable across releases (e.g. `architecture-depcruise`),
so the split-screen diff and prev/next walk line up.

## Failure modes

- **Runtime missing (Node/Docker/dotnet/cargo)** → exit `3`; the script
  printed the exact install command and the pinned run line. Never
  auto-install; install once, re-run.
- **Every analyzer runtime missing** → each runner still exits `3`; switch to
  the [tool-free fallback](#tool-free-fallback). The Skill never fails solely
  because no analyzer is installed.
- **Tool ran, output unparseable** → exit `2`; the raw file is kept. Inspect
  it, adjust the target, re-run.
- **Blocking layering violation found** → exit `4`, `status: error`, fragment
  still written — the analysis succeeded; the finding is what is bad.
- **Target invalid** (not a dir / no `Cargo.toml` / no `nx.json` / no `.dsl`)
  → exit `5`, nothing written.
- **Graph too large to render inline** → over 300 nodes, the `d3-graph` is
  replaced by a note; `metrics{}` and the cycle/violation tables remain
  authoritative.
- **F# codebase** → reflection rules unreliable; use Structurizr DSL instead.

## Exit codes

Every runner and `to-fragment.py`:

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Tool ran but output unparseable; raw kept for diagnosis. |
| `3`  | Required runtime/Docker missing; install + pinned run line printed. |
| `4`  | Tool ran and reported a blocking violation; fragment written, `status: error`. |
| `5`  | Target invalid (not a dir, wrong project marker, missing DSL). |
