# Help: Report build status

This report part answers one question: did every producer that feeds this
release report actually run? It is the report's own self-check, pinned in the
`report` nav area right after the overview.

## How to read it

- **Status.** `error` means at least one producer failed — a report part is
  missing or incomplete, so the report you are reading is partial. `warn`
  means at least one producer was skipped (its tool or Docker was absent), so
  that area is unmeasured rather than clean. `ok` means every producer ran.
- **Metric cards.** How many producers ran in total, and the split across
  ok / failed / skipped.
- **Producer build status table.** One row per producer: the skill, the
  fragment id it was meant to stage, its outcome, the exit code, and the last
  line of its output. The table's heading icon mirrors the worst outcome.

## Outcome meanings

- **ok** — the producer ran and staged its fragment.
- **failed** — the producer ran but errored; its fragment is missing or
  unreliable. Anything that part would have told you is unknown.
- **skipped** — the producer's tool or Docker image was not available, so it
  did not run. The area is unmeasured, which is a gap, not a pass.

## Release decision

When the synthesis role has run, this part also carries an "Open questions &
inferences" section and an advisory decision checklist: a human-readable
judgment of whether the release decision can still be made given the gaps,
and what to confirm first. That section is advisory — the pipeline does not
act on it.

## What this part does not tell you

Whether the findings inside each report part are good or bad — only whether
the part was produced at all. A green build status with a failing security
report still means the release has a security problem.
