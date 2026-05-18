# Reading the mission-alignment fragment

This part answers one question: does the work in this release serve a stated
product mission? It is documentation coverage plus an alignment narrative, not
a code finding.

## Mission documents found

The repository's product-intent documents (MISSION.md, PRODUCT.md, VISION.md,
`docs/vision|mission|product|strategy|roadmap`, OKR/PRD files) with their word
count and whether each is `substantive` or a `thin` stub.

What to look for: at least one `substantive` document. A table that is empty,
or only `thin` rows, means the mission is undocumented — the fragment then
carries the reflection questions instead, and alignment cannot be assessed.

What it means: the count of substantive documents is the `mission_docs_found`
metric. Zero is `status: info` (a gap to fix, not a failure); one or more lets
the role map changes to goals.

## Mission documentation gap

Present only when no substantive mission document exists. It lists the
reflection questions a team should answer — purpose, audience, outcome,
explicit non-goals, how progress is measured, stated-goal-vs-speculative per
change.

What to look for: treat the questions as the deliverable. Answering them in a
committed `MISSION.md` turns the next run's `info` into an assessable result.

## Alignment narrative (role-written)

The `mission-alignment` role adds a narrative section: the derived goal set,
whether the change set serves it, a per-change mapping, and any scope-creep
flags (a change that advances an explicit non-goal, or adds a capability no
stated goal covers).

What to look for: unmapped changes and scope-creep flags. `changes_unmapped`
or `misalignments` above zero is `status: warn` — work is drifting from the
stated mission, not blocked.
