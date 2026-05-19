# Mission document locations

The configurable set `inventory-mission.sh` searches for product-intent
documentation, how to point it at a document outside the repo, and a minimal
`MISSION.md` template so a detected gap is immediately actionable.

## Default search set

`inventory-mission.sh` resolves these globs relative to the repository root
(forward slashes only, case as written; the first match in each glob wins):

| Glob | Intent |
| ---- | ------ |
| `MISSION.md` | The mission statement at the root. |
| `PRODUCT.md` | Product definition / north star. |
| `VISION.md` | Longer-horizon vision. |
| `docs/vision*` | Vision docs under `docs/`. |
| `docs/mission*` | Mission docs under `docs/`. |
| `docs/product*` | Product definition under `docs/`. |
| `docs/strategy*` | Strategy / direction docs. |
| `docs/roadmap*` | Roadmap (goal sequencing). |
| `docs/okr*`, `OKR*.md` | Objectives and key results. |
| `docs/prd*`, `PRD*.md` | Product requirements documents. |

A document shorter than 40 words counts as **thin**: it is recorded in the
inventory but does not raise `mission_docs_found`, so a stub `MISSION.md` does
not mask the gap. `mission_docs_found` is the count of substantive documents.

## Pointing at an external document

When the mission lives outside the repository (a shared wiki exported to a
file, a vendored copy, a path in a monorepo sibling), set `MISSION_DOC` to its
absolute path before running the script:

```bash
MISSION_DOC=/abs/path/to/exported-mission.md \
  bash scripts/inventory-mission.sh <repo> <out_dir> [ref-range]
```

The pointed-at file is added to the inventory first, then the default globs
run. Use a forward-slash path. Only a single external document is supported;
commit it into the repo if more than one matters.

## Minimal MISSION.md template

When the inventory reports a gap, adding this file at the repository root makes
the next run map changes to goals instead of emitting the reflection
questions. Replace every bracketed field; keep it under one page.

```markdown
# Mission

## Purpose

[One sentence: the problem this product solves.]

## Audience

[Who this is for and what they need from it.]

## Outcome

[What success looks like — the observable end state.]

## Goals

- [Goal 1 — a capability or outcome the product is driving toward.]
- [Goal 2]
- [Goal 3]

## Non-goals

- [Something this product explicitly will not do.]
- [Another deliberate boundary.]

## How progress is measured

[The signal(s) that indicate the mission is being advanced.]
```

## Out of scope

Judging whether a found document is *good*, mapping changes to goals, or
flagging scope creep — that is the `mission-alignment.md` role. Rendering or
fragment shape — that is `to-fragment.py` and the framework. Discovering a
"vibe coder" definition — that is `dev-analysis-evolution`'s concern, not this
Skill's.
