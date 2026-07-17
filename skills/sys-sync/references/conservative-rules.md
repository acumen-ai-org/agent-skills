# Conservative rules — when a sync actually updates something

The bar: an artifact is updated only when one of its **statements is now
false**, not when it could be richer. Refinement pressure is the failure
mode this skill exists to resist.

## Changes that DO warrant updates

- A component the report inventories was **added or removed** (an app, a
  framework, a module, a pipeline, a k8s workload, a data-model type).
- An **architecture relationship changed** (a plane split or merged, a
  dependency direction reversed, a store replaced).
- A **route/page/section count or list** shown in a report is now wrong
  by more than noise (a whole feature area appeared or disappeared —
  not one helper endpoint).
- A required document's subject was **restructured or renamed** so the
  document misleads (not merely under-describes).
- The change itself **created a doc-set gap**: a new framework/module
  shipped without its required README/setup/operations docs.

## Changes that NEVER warrant updates

- Refactors, bug fixes, performance work, dependency bumps, lint/style.
- New helper functions, small endpoints, internal reshuffling within an
  existing component.
- Anything that only makes existing statements *less complete* rather
  than false.
- Line-count/statistics drift in reports (stats are snapshots by
  design; they update when a report updates for a real reason).
- Pre-existing doc gaps the current change did not cause — flag them in
  the summary, one sentence, and move on.

## When updating a report

- Follow the canon skeleton and component rules
  (`<canon>/system/frameworks/reports/docs/authoring.md`).
- Edit the smallest set of pages/sections whose statements broke; do
  not regenerate wholesale.
- Update the provenance line (date + commit) — an in-place report's
  provenance is its "last updated" marker.
- Restate any changed chart numbers in captions (offline rule).

## When in doubt

Do nothing except advance the sync point and say why in one sentence.
