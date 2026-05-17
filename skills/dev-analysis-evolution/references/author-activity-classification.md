# Role: Per-author activity classification (dev-analysis-evolution)

Recommended model: a mid-tier model — bounded classification against fixed
taxonomies, not open-ended reasoning.

You classify every PR-unit in the evidence bundle from
`collect-author-activity.sh`. The taxonomies are fixed so the fragment is
comparable release-over-release. You add classification fields to each
PR-unit and emit the augmented bundle as JSON; `to-fragment.py` reads it.

## Contents

- [When invoked](#when-invoked)
- [Input](#input)
- [PR type taxonomy](#pr-type-taxonomy)
- [Pattern-use taxonomy](#pattern-use-taxonomy)
- [Vibe coder](#vibe-coder)
- [Output](#output)
- [Worked example](#worked-example)
- [Hard rules](#hard-rules)
- [Out of scope](#out-of-scope)

## When invoked

After `collect-author-activity.sh <repo> <out_dir> <ref_range>` wrote
`<out_dir>/author-activity.json`. The caller passes you that bundle and writes
your verbatim JSON to `<out_dir>/author-activity.classified.json`.

## Input

The `author-activity.json` bundle: `strategy`, `pr_unit_count`,
`vibe_coder_definition` (object with `path`+`text`, or `null`), and `pr_units[]`.
Each PR-unit has: `author` (canonicalized), `pr`, `title`, `body`,
`work_items[]` (each `{id, type}` — `type` may be `null`), `changed_paths[]`,
`numstat[]`, and `static_pattern_hint{ new_files_in_new_directories,
new_top_level_modules, edits_to_existing_files }`.

## PR type taxonomy

Exactly one per PR-unit:

| Type | Definition |
| ---- | ---------- |
| New feature | Introduces a user-facing capability not previously present. |
| Updated feature | Modifies or extends an existing user-facing capability. |
| Bug | Corrects incorrect behavior; no new capability. |
| Technical | Refactor, performance, build, dependency bump, tests, CI, internal tooling; no intended behavior change. |
| Configuration | Changes to config / IaC / manifests / feature flags only. |
| Data | Schema / migration / seed / fixture / content-data changes only. |

**Signal priority.** When a PR-unit has a resolved Azure work-item `type`,
that is the primary signal:

- `Bug` → Bug.
- `User Story` / `Feature` / `Product Backlog Item` → New or Updated feature,
  split by the new-vs-existing diff evidence (see pattern-use).
- `Task` → Technical unless the diff clearly shows otherwise.

Title/body/diff disambiguate and override only on strong evidence. With no
resolved type, classify from title/body intent weighted by diff size
(`numstat`, `changed_paths`). Tie-break toward the most user-visible type:
**New feature → Updated feature → Bug → Data → Configuration → Technical**.

## Pattern-use taxonomy

For New/Updated feature PRs only, exactly one. Non-feature PRs leave it `""`.

| Value | Definition |
| ----- | ---------- |
| New patterns | Introduces a new module/package/top-level component, a new architectural pattern, or a new cross-cutting abstraction. |
| Existing patterns, components and modules | Implemented by extending or reusing existing modules, components, and established patterns. |

Use `static_pattern_hint` plus the diff: high
`new_files_in_new_directories` / `new_top_level_modules` relative to
`edits_to_existing_files` points to **New patterns**; mostly edits to existing
files points to **Existing patterns, components and modules**.

## Vibe coder

Per author, assigned **only** when the bundle's `vibe_coder_definition` is
non-null. Apply that definition's criteria verbatim — never supply your own.
With `vibe_coder_definition: null`, set every author's `vibe_coder` to the
literal string `undetermined — no repository definition found` and set
top-level `vibe_coders` to `0` only if you also set
`vibe_coder_definition_found: false`. When a definition exists, `vibe_coders`
is the count of authors meeting it.

## Output

Output only — no commentary. A single JSON object, the input bundle with
these additions, nothing removed:

- top-level `vibe_coder_definition_found`: boolean.
- top-level `vibe_coders`: integer (0 when no definition).
- each `pr_units[i]` gains:
  - `pr_type`: one of the six exact strings above.
  - `pattern_use`: one of the two exact strings, or `""` for non-feature.
  - `classification_basis`: one short sentence citing the signal used
    (resolved work-item type, title/body, or diff).
- each distinct author gains an entry in a top-level `authors[]` array:
  `{ "author": <name>, "vibe_coder": <verbatim-definition-verdict |
  "undetermined — no repository definition found"> }`.

Emit valid JSON only — it is written to a file and parsed.

## Worked example

Input PR-unit:

```json
{ "author": "Alice Doe", "pr": 16644,
  "title": "Add inline editor feature toggle",
  "body": "Add inline editor feature toggle",
  "work_items": [ { "id": 29732, "type": "Product Backlog Item" } ],
  "changed_paths": ["src/feature.py"],
  "static_pattern_hint": { "new_files_in_new_directories": 0,
    "new_top_level_modules": 1, "edits_to_existing_files": 0 } }
```

Classified:

```json
{ "...": "all input fields preserved",
  "pr_type": "New feature",
  "pattern_use": "New patterns",
  "classification_basis": "Work-item type Product Backlog Item; new top-level module per static hint." }
```

## Hard rules

- Output only — valid JSON, no prose, no code fences in the actual output.
- Exactly one `pr_type` per PR-unit from the six strings, verbatim.
- `pattern_use` set only for New/Updated feature; `""` otherwise.
- Vibe coder is assigned only from a present repo definition, applied
  verbatim; otherwise the undetermined string. Never invent the label.
- Preserve every input field; only add the fields listed under Output.

## Out of scope

The evolution metrics narrative (that is `evolution-narrative.md`). Locating
the vibe-coder definition (that is the collector +
`vibe-coder-definition-locations.md`). Rendering or section-type choice.
