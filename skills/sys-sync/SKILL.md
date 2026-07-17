---
name: sys-sync
description: Keeps a repository's in-place HTML reports and required documents aligned with the code after considerable changes, per the Acumen ways of working. Deliberately conservative — it updates nothing when changes merely refine what already exists, and always advances the sync point so the Stop hook goes quiet. Triggered by the plugin's Stop hook when watched change volume crosses the repo's sys.json threshold; can also be run on demand. Use when the Stop hook asks for it, or when you want a manual docs/reports freshness pass.
---

# sys-sync

A thin, conservative synchronizer. The premise (canon:
`<canon>/system/docs/transparency.md`): slightly stale documents are
acceptable; documents that state something now false are not.

## Steps

1. **Load context.** Read `sys.json` at the repo root (`canon`, `watch`,
   `exclude`; `canon: "."` means this repo) and
   `.ai/sys-sync-state.json` (`lastSyncCommit`). Summarize what changed:
   `git diff --stat <lastSyncCommit>..HEAD` plus the working tree,
   restricted to watched paths.

2. **Judge conservatively.** Read
   [references/conservative-rules.md](references/conservative-rules.md)
   and decide per artifact whether any of its *statements* are now
   false. When in doubt, do not update.

3. **If (and only if) statements broke:**
   - Update the affected in-place reports (`{topic}-index.html` in the
     folders they describe) following the canon's authoring rules at
     `<canon>/system/frameworks/reports/docs/authoring.md` — including
     the provenance line (date + current commit). Never touch
     procedural reports under `.ai/reports/`.
   - Restore the required document set for any level whose docs the
     change invalidated or removed, per the levels table in
     `<canon>/system/docs/transparency.md`. Create missing required
     documents only when the change itself introduced the gap (a new
     framework, a new module); pre-existing gaps are flagged in one
     sentence, not silently filled.

4. **Always advance the sync point.** Write
   `.ai/sys-sync-state.json` with `lastSyncCommit` = current HEAD
   (keep `turnsSinceTrigger` as-is). This happens even when nothing
   was updated — it is what makes the hook quiet again.

5. **Report in one short paragraph**: what was judged, what was
   updated (or that nothing needed updating), and the new sync point.
