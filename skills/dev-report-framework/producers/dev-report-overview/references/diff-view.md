# Role: Diff view perspectives

Recommended model: a reasoning-capable model — this is judgment over the
release's user-visible and contract-level deltas, expressed as terse
before/after pairs, not extraction.

You read the release's raw change data (commits, changed files, and — when
present — the deterministic classifier output `changes_shifts.json` and the
`author-activity.classified.json` PR units) and produce the Overview
`diff_view.perspectives[]`: one block per perspective, each a small set of
`{before, after}` items a reviewer word-diffs at a glance.

## Contents

- [When invoked](#when-invoked)
- [Inputs](#inputs)
- [The perspectives](#the-perspectives)
- [Item rules](#item-rules)
- [Determinism](#determinism)
- [Output](#output)
- [Hard rules](#hard-rules)
- [Out of scope](#out-of-scope)

## When invoked

During Overview synthesis, after `classify-changes.py` has written
`<work-dir>/changes_shifts.json`. Its output feeds the
`change-shift-narrative` role, which merges it into `overview-extras.json`.

## Inputs

- `<work-dir>/commits.txt`, `<work-dir>/changed-files.txt` — the release's
  raw change surface.
- `<work-dir>/changes_shifts.json` — the deterministic groups and shift rows.
- `<work-dir>/author-activity.classified.json` — present only when
  dev-analysis-evolution ran; per-PR `pr_type`, `work_items[]`,
  `changed_paths[]`.
- The orchestrator states whether `reports.workflowDocsGlob` is set in
  `dev-process.json`. It is OPTIONAL config the orchestrator passes through;
  do not add it to any schema. When unset, the `workflow` perspective is
  dropped entirely.

## The perspectives

The core set is four; the set is open — a deployment may add further
perspectives (e.g. operability, data/migration, compliance) with their own
`slug`/`title`/`lead`. Every perspective obeys drop-if-empty.

| slug | covers | primary sources |
|---|---|---|
| `user` | what end users see/do and why | user-visible diffs, work-item descriptions |
| `arch` | structural / security / infra changes | the classifier's shift rows |
| `product` | capabilities added / retired / reshaped | features, deprecations, removed public API |
| `workflow` | documented user-workflow step changes | changed paths vs `reports.workflowDocsGlob` |

`workflow` is included only when the orchestrator says
`reports.workflowDocsGlob` is set; otherwise omit it (no header, no
placeholder). Keep slugs generic — never name a product, company, or internal
module.

## Item rules

Change kind is implicit in the pair: empty `before` ⇒ NEW; empty `after` ⇒
DELETED; both present ⇒ UPDATED.

- Each entry ≤ 12 words. For UPDATED, `before` and `after` are each ≤ 12 words
  and differ by a small word-level delta so the inline word-diff stays
  readable (change the few words that changed, keep the rest aligned).
- Noun phrase or contrasted state only. No leading articles ("the", "a"); no
  boilerplate verbs ("This change adds…", "We now support…").
- Do not fabricate. Touching a file is not an UPDATED item — only a
  user-visible behavior change, a public-contract change, or a
  documented-workflow step change counts. A perspective with no real items is
  omitted entirely.

## Determinism

Pin the generation: `temperature 0`, `top_p 1`, `seed 42`, a hard output cap,
and a JSON-schema-shaped response when the model supports it. The same release
input yields the same perspectives so the content-to-image cache and the
release-over-release diff stay stable.

## Output

Output only — no preamble. JSON, exactly this shape:

```json
{ "perspectives": [
    { "slug": "user", "title": "User perspective (need)",
      "lead": "What end users see and do.",
      "items": [ { "before": "", "after": "Composition edit-mode panel" } ] }
] }
```

Emit only perspectives that have at least one real item; never emit an empty
`items` array and never an item with both `before` and `after` empty —
`to-fragment.py` rejects either.

## Hard rules

- Output only — the JSON object, no commentary.
- ≤ 12 words per field; UPDATED pairs differ by a small word delta.
- Drop-if-empty and do-not-fabricate apply to every perspective.
- Generic, vendor-neutral wording; no product/company/module names.
- Counts, signals, and module ids are the classifier's — never restate or
  re-derive them here; this role writes only the before/after items.

## Out of scope

Computing change groups, shift signals, or module folding (that is
`classify-changes.py`). Writing `overview-extras.json` or merging
(`change-shift-narrative`). Fragment shape, menu, or the data: URI
(`to-fragment.py`). Hero imagery (`hero-briefs.md`).
