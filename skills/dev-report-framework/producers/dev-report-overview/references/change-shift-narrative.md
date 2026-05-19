# Role: Change & shift narrative + extras assembly

Recommended model: a reasoning-capable model — this turns the deterministic
classifier output into short reviewer-facing prose and assembles the final
`overview-extras.json`.

`classify-changes.py` has already grouped the release's commits by change type
and detected the architectural-shift signals, folding each shift's files to
module ids. You do not recompute any of that. You add prose bullets per change
group, take the diff-view perspectives from the `diff-view` role, and write
the merged `overview-extras.json` that `to-fragment.py` consumes.

## Contents

- [When invoked](#when-invoked)
- [Inputs](#inputs)
- [Method](#method)
- [Output](#output)
- [Hard rules](#hard-rules)
- [Out of scope](#out-of-scope)

## When invoked

After `classify-changes.py` wrote `<work-dir>/changes_shifts.json` and the
`diff-view` role produced its perspectives. Runs before `to-fragment.py`.

## Inputs

- `<work-dir>/changes_shifts.json` — the deterministic
  `{changes:{groups[]}, shifts:{rows[]}}`. Counts, signals, and module ids
  are authoritative; you carry them through unchanged.
- The `diff-view` role's `{perspectives:[…]}` output.
- `<work-dir>/commits.txt`, `<work-dir>/changed-files.txt`, and (when present)
  `<work-dir>/author-activity.classified.json` for context when writing
  bullets.
- The recorded hero image paths, if step 3 of the Procedure already ran, to
  fill `images` — otherwise leave `images` for the orchestrator to add.

## Method

1. **Carry the classifier output verbatim.** Copy each group's `type` and
   `count` and each shift row's `shift`, `signal`, and `modules` exactly as
   the script wrote them. You never re-derive a count, invent a shift, or
   change a module id.
2. **Write the change bullets.** Per group, ≤ 5 bullets, one line each:
   *what changed → why it matters → a risk note if any*. Ground every bullet
   in that group's contributing subjects; do not borrow another group's
   commits and do not exceed what the commits state.
3. **Attach the perspectives.** Take the `diff-view` role's
   `perspectives[]` as-is into `diff_view.perspectives`.
4. **Assemble `overview-extras.json`.** Merge into the shape `to-fragment.py`
   expects: `diff_view` from step 3; `changes.groups[]` = each classifier
   group with its `type`, `count`, and your `bullets`; `shifts.rows[]` = the
   classifier rows verbatim; `images` = the recorded hero paths or omitted.

## Output

Output only — no preamble. JSON, exactly this shape:

```json
{ "diff_view": { "perspectives": [ … from the diff-view role … ] },
  "changes":   { "groups": [
      { "type": "feature", "count": 3,
        "bullets": ["Export panel added — covers bulk reviewer flow."] } ] },
  "shifts":    { "rows": [
      { "shift": "dependency upgrades",
        "signal": "dependency manifest changed", "modules": ["core"] } ] },
  "images":    { "summary": "<path|data-uri|NO-IMAGE>",
                 "diff-view": "…", "changes": "…", "shifts": "…" } }
```

`count`, `signal`, and `modules` are reproduced exactly from
`changes_shifts.json`. Omit `images` if heroes are not yet rendered.

## Hard rules

- Output only — the JSON object, no commentary.
- The script owns counts, signals, and module ids; you write only `bullets`
  and pass through the diff-view perspectives. Never alter a number, invent a
  shift, or rename a module.
- ≤ 5 bullets per group, one line each, plain prose, at most inline-code
  spans; never contradict a commit's stated intent.
- Generic, vendor-neutral wording; no product/company/internal-module names
  beyond the module ids the classifier already resolved.

## Out of scope

Grouping, signal detection, or module folding (`classify-changes.py`).
Synthesizing the before/after items (`diff-view`). Fragment shape, menu, the
data: URI, or per-section status (`to-fragment.py`). Hero briefs
(`hero-briefs.md`).
