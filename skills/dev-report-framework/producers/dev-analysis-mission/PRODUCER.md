# dev-analysis-mission

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

Locates product-intent documents, captures their content and factual metrics,
and (with a ref-range) the change inventory. A deterministic script writes the
factual fragment; the [`mission-alignment`](references/mission-alignment.md)
role enriches `summary` and adds the alignment narrative. The Skill is
self-contained — no external registered subagent.

Critical behavior: a repository with **no or only thin** mission documentation
is not an error. The fragment is `status: info`, its `summary` is "No product
mission documentation found", and its body lists the reflection questions a
team should answer (purpose, audience, outcome, explicit non-goals, how
progress is measured, stated-goal-vs-speculative per change).

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [The configurable search set](#the-configurable-search-set)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input          | Default | Notes |
| -------------- | ------- | ----- |
| `<repo>`       | —       | Path to the git repository to inventory. Positional arg 1. |
| `<out_dir>`    | —       | Where `mission.raw.json` and the fragment land. Positional arg 2. |
| `[ref-range]`  | unset   | Optional git range (e.g. `v2026.04.0..main`). When given, the change inventory (changed areas + commit subjects) is collected. Positional arg 3. |
| `MISSION_DOC`  | unset   | Env var: absolute forward-slash path to a mission document outside the repo. Added to the inventory before the default globs. See [`references/mission-doc-locations.md`](references/mission-doc-locations.md). |

No external engine: pure `bash` + `python3` (standard library only) + `git`.
No Docker.

## Procedure

Track progress:

```
- [ ] 1. Inventory   → <out_dir>/mission.raw.json
- [ ] 2. To-fragment → <out_dir>/mission.fragment.json
- [ ] 3. Validate    (feedback loop — must exit 0)
- [ ] 4. Synthesis   (mission-alignment role enriches the fragment)
```

### 1. Inventory

```bash
bash "scripts/inventory-mission.sh" <repo> <out_dir> [ref-range]
```

Locates mission docs via [the configurable search
set](#the-configurable-search-set), captures full content + `metrics{}`, and —
when `ref-range` is given — the changed areas and commit subjects. Writes
`<out_dir>/mission.raw.json`. The trailing `TOOL inventory-mission exit=<n>`
line reports status; exit `5` means the repo or ref-range is invalid.

### 2. To-fragment

```bash
mkdir -p <fragments_dir>
python3 "scripts/to-fragment.py" mission \
  <out_dir>/mission.raw.json <fragments_dir>/mission-alignment.fragment.json
```

The fragment lands in a **separate** `<fragments_dir>`, never alongside
`mission.raw.json` — `validate_fragments.py` validates every `*.json` in the
directory it is pointed at, and the raw inventory is not a fragment.
Normalizes the inventory into a [report
fragment](../../references/fragment-schema.md). No
substantive docs → `status: info`, the reflection-questions body. Substantive
docs with unmapped changed areas → `status: warn`; none to map → `status: ok`.
The script never calls an LLM.

### 3. Validate (feedback loop)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <fragments_dir>
```

Exit `0` → proceed. Exit `3` → per-file errors on stderr; fix
`to-fragment.py` output and re-run. Do not proceed to synthesis or a build
until this exits `0`.

### 4. Synthesis (role)

Follow [`references/mission-alignment.md`](references/mission-alignment.md)
with `mission.raw.json` and the provisional fragment as input. Run it inline,
or — for fresh context — delegate it to an isolated agent passing the role
file's contents as instructions. Apply the role's `## Summary` line to the
fragment's `summary`, append its narrative as one `markdown` body section, and
set `metrics.changes_mapped` / `changes_unmapped` / `misalignments` and
`status` to the role's corrected counts. Re-run step 3 after editing.

When the fragment is already `status: info` (no docs), the role only confirms
the gap and notes any thin stub — the reflection questions are the
deliverable; nothing is mapped.

## The configurable search set

The default globs, the `MISSION_DOC` external-pointer mechanism, the
thin-document threshold, and a minimal `MISSION.md` template live in
[`references/mission-doc-locations.md`](references/mission-doc-locations.md).
Edit that file to change what counts as a mission document — the script reads
the same set it documents.

## Outputs

- `<out_dir>/mission.raw.json` — the factual inventory (documents with full
  content, substantive count, change inventory, metrics). An intermediate, not
  a fragment — keep it out of the validated `<fragments_dir>`.
- `<fragments_dir>/mission-alignment.fragment.json` — one `category: mission`
  fragment, id `mission-alignment`, with
  `metrics{ mission_docs_found, changes_mapped, changes_unmapped,
  misalignments }`. `status` is `ok` (aligned), `warn` (unmapped changes or
  scope creep), or `info` (no/thin docs → reflection questions).

The fragment id is stable across releases so the report split-screen diffs
`mission_docs_found` and the mapping counts release-over-release.

## Failure modes

- **No or only thin mission docs** → not a failure. `status: info`, summary
  "No product mission documentation found", body lists the reflection
  questions. This is the expected outcome on a repo without a mission doc.
- **`ref-range` invalid** → script exits `5`, no fragment written; fix the
  range (it must resolve in `<repo>`).
- **`<repo>` not a git work tree / `git` missing** → exit `5` with the cause
  on stderr.
- **`mission.raw.json` unparseable** → `to-fragment.py` exits `2`, raw kept
  for diagnosis, no fragment written.
- **A document outside the repo** → set `MISSION_DOC` to its absolute path;
  without it, only in-repo globs are searched.

## Exit codes

`inventory-mission.sh` and `to-fragment.py` mirror the standard runner codes.

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment written; `status` `ok` / `warn` / `info`. |
| `1`  | Bad arguments (missing positional / wrong category arg). |
| `2`  | Inventory ran but `mission.raw.json` unparseable; raw kept. |
| `3`  | Not used by this Skill (no required external tool to install). |
| `5`  | `<repo>` not a git repository, `git` missing, or `ref-range` invalid. |

Code `4` is unused: this Skill's `status` is never `error` — a documentation
gap is `info`, drift is `warn`, neither is a blocking finding.
