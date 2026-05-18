# Reading the evolution and author-activity report

These two fragments describe how the repository changed across releases from
git history alone: per-release-pair churn, what files moved by extension, who
changed what, and how each PR is classified.

## What to look for

- **Extension → folder → file tree.** Level-1 rows are file extensions with
  their total changed-file count over the whole range; expand to folders, then
  to individual files. The `Module` column composes with the global module
  selector — pick a module to narrow the tree to its folders and files.
- **Per-release-pair churn.** One row per adjacent release pair: files changed,
  lines added, lines removed. This is the change *this release introduces*; it
  sits in the right vs-production column.
- **Change-concentration treemap.** Bigger tiles are extensions absorbing more
  of the change. A few dominant tiles mean concentrated change; an even spread
  means broad change.
- **Per-author summary and Author × PR-type heatmap.** PR counts per author
  split by type. The heatmap reads at a glance — a bright row is an author
  driving most of one type.
- **Per-PR detail.** One row per PR per module it touched (a multi-module PR
  repeats, one row per module). The work-items column links to the tracker when
  the repo has Azure DevOps configured, and is plain text otherwise.

## What it means

- **code-maat sections are optional.** Their absence means Docker was
  unavailable when the report ran, not that coupling or churn was zero.
- **`vibe coder: undetermined`** means the repository ships no definition for
  the term — the label is never invented, so undetermined is the honest state,
  not a failure.
- **Empty PR-type / pattern columns** mean the classification role did not run;
  the activity counts are still accurate, only the per-PR labels are absent.
- **A PR with no changed paths** yields one module-agnostic row that no module
  filter hides — expected for empty or revert-only squashes.
- **Linked vs plain work items.** A linked id confirms tracker integration is
  configured for this repo; plain text simply means it is not — both are
  contract-valid.

## Status

These fragments report observed history; status stays `ok`. Read the churn and
concentration together to judge whether the change is broad or concentrated.
