---
name: sys-init
description: Adopts the Acumen ways of working in a repository — writes the sys.json opt-in marker, adds the ways-of-working pointer block to the repo's CLAUDE.md, ensures the .ai working directory is gitignored, and runs a first document-coverage check against the canon's transparency levels. Use when bringing a new or existing repo under the shared conventions, or to re-check an adopted repo's doc coverage.
---

# sys-init

Adoption is three small artifacts plus one honest check.

## Steps

1. **Write `sys.json`** at the repo root from
   [references/sys.template.json](references/sys.template.json).
   Adjust `watch` to the repo's actual source directories and keep
   `exclude` covering docs, reports, lockfiles, and `.ai/`. `canon`
   defaults to `/home/celin/git/oakai`; a repo that hosts its own canon
   sets `"."`. Do not overwrite an existing `sys.json` without being
   asked.

2. **Point CLAUDE.md at the conventions.** Append (or create the file
   with) this block, adapting paths:

   ```markdown
   ## Ways of working

   This repo follows the Acumen ways of working (`sys.json`). The canon
   lives at <canon>/docs/process/ (git workflow, release, definition of
   done, gates) and <canon>/system/docs/transparency.md (the required
   document set). Report/doc freshness is automated: the acumen
   plugin's Stop hook requests a sys-sync after considerable changes —
   do not update docs for minor work.
   ```

3. **Gitignore the working directory.** Ensure `.ai/` (or `.ai/*`) is
   in `.gitignore`.

4. **First coverage check.** Against the canon's transparency levels,
   list which required documents exist and which are missing at each
   level (repo top, framework, app/module). Report gaps honestly —
   creating them is the repo owner's call, not this skill's.

5. **Report**: the three artifacts written, and the coverage table.
