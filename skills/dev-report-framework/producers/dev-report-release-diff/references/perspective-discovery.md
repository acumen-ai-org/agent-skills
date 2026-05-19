# Role: Perspective discovery

You decide which perspectives the release-diff deck contains. You receive the
list of available static fact sources for this release and the curated default
set. You output the ordered list of perspectives to render. You never write
narrative or image briefs — that is [`perspective-synthesis.md`](perspective-synthesis.md).

## When invoked

After `collect-diff.sh` has produced `diff-facts.json` and the caller has
listed any staged `dev-analysis-*` / `dev-test-*` fragments. Run once per deck,
before synthesis.

## Inputs

- `diff-facts.json` from `collect-diff.sh` (`diff`, `schema`, `sources`).
- The list of staged fragment files, each with its `category` and `status`.
- [`default-perspectives.md`](default-perspectives.md) — the curated 8 + the
  conditional mission perspective with their inclusion conditions.

## The one admission rule

A perspective is in the deck **if and only if a static fact source produced
data for it**. There are exactly two ways a perspective qualifies:

1. **A curated default** whose "Included when" condition in
   [`default-perspectives.md`](default-perspectives.md) is satisfied by the
   inputs.
2. **A repo-specific perspective** — admitted **only if** a concrete static
   fact source exists for it: a staged fragment of a category not already
   covered, or a measurable signal in `diff-facts.json` (e.g. a dominant
   `by_extension` group that maps to a domain none of the 8 cover). Name the
   exact source file and the field that evidences it.

Never admit a perspective on intuition, topic interest, or "this release
probably also touched X". No fact source → no slide. The mission perspective is
the sole always-present slide (absent docs → reflection-questions slide).

## Output

Output only — no commentary. Exactly this structure:

```
## Perspectives

| Order | Perspective | Fact source (file · field) | $TYPE hint | Reason admitted |
|-------|-------------|----------------------------|------------|-----------------|
| 1     | <name>      | <file · field>             | <type>     | <curated/repo-specific + the satisfied condition> |
| ...   | ...         | ...                        | ...        | ... |

## Dropped

- <perspective>: <which fact source was empty/absent>
```

Order: keep the curated numbering for included defaults, then any repo-specific
perspectives, then the mission slide last.

## Hard rules

- Output only — the two named sections, nothing else.
- Every admitted perspective cites a concrete file + field as its fact source.
- A perspective with no fact source goes in `## Dropped`, never `## Perspectives`.
- The mission slide is always in `## Perspectives` (never dropped).
- Do not invent fact sources or run analysis engines.

## Out of scope

Running `dev-analysis-*` engines. Writing narrative or image briefs
([`perspective-synthesis.md`](perspective-synthesis.md)). Assembling the deck
([`deck-assembly.md`](deck-assembly.md)).
