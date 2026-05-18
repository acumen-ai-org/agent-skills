# Reading the vs-production column

This step does not produce its own fragment. It backfills the right
**vs production** column of fragments whose producer emitted only a left
**This release** view, by diffing each against its same-id counterpart from the
previous release.

## What to look for

- **The "vs production" markdown section.** A concise summary of what changed
  in this fragment relative to the last release that shipped it — the
  release-over-release delta in prose, not a re-statement of the current state.
- **The "vs production" image.** A one-shot infographic of that delta. It
  always renders: a real illustration on success, or a diagnostic fallback
  image carrying the provider and HTTP status when generation failed.
- **Which fragments gained a column.** Only fragments that (a) lacked any
  production view and (b) had a prior same-id counterpart are augmented. A
  fragment with no right column is new this release or already carried one.

## What it means

- **An empty vs-production column on the first release is expected.** With no
  prior report there is nothing to diff; the column stays empty and that is the
  documented no-op, not a gap.
- **A new fragment has no delta.** A report part shipping for the first time
  has no prior counterpart, so no vs-production section is added — there is
  nothing to compare it to yet.
- **The appended sections are `status: info`.** They are commentary on the
  delta, not a pass/fail judgement; the fragment's own `status` and `metrics`
  are unchanged by this step.
- **A fallback image** means generation failed but the summary still shipped —
  read the markdown; the image carries the failure detail, not the delta.

## Status

This step changes no fragment's own status. The backfilled sections are
`status: info` (the image section omits status). Read the markdown for the
release-over-release story; the left column still holds the current state.
