# Ways of working — the sys layer

The plugin carries the automation that keeps Acumen repos aligned with a
shared way of working. The **canon itself lives in the oakai repo**
(local reference for now, by decision — revisit when the canon should
travel with the plugin):

- `<canon>/docs/process/` — git workflow, release process, definition
  of done, merge gates.
- `<canon>/system/docs/transparency.md` — the required document set per
  level and the reports rule.
- `<canon>/system/frameworks/reports/` — the self-sufficient HTML
  report framework the in-place reports follow.

Default canon path: `/home/celin/git/oakai`, overridable per repo in
`sys.json`.

## The pieces

| Piece | What it does |
| --- | --- |
| `sys.json` (per repo) | The opt-in marker and config: `canon`, `threshold` (default 300 changed lines), `cooldown` (default 10 turns), `watch`/`exclude` globs. No `sys.json` → every hook below is a silent no-op. |
| `hooks/sys-session-start.sh` (SessionStart) | Injects one context message into sessions in opted-in repos: where the canon is, that doc freshness is automated and deliberately conservative. |
| `hooks/sys-sync-stop.sh` (Stop) | Cheap, deterministic, every turn: counts changed lines in watched paths since the last sync point (`.ai/sys-sync-state.json`, gitignored). At ≥ threshold and past the cooldown it blocks the stop once and asks the agent to run sys-sync. Guards: `stop_hook_active`, missing git repo, first run seeds the sync point silently. |
| [skills/sys-sync](../skills/sys-sync/SKILL.md) | The judgment layer: updates in-place reports and required docs **only** when the changes made their statements false (rules in the skill's `references/conservative-rules.md`), and always advances the sync point. |
| [skills/sys-init](../skills/sys-init/SKILL.md) | Adopts a repo: writes `sys.json`, adds the CLAUDE.md pointer block, gitignores `.ai/`, runs a first doc-coverage check. |

## The freshness philosophy

Slightly stale documents are acceptable; documents that state something
now false are not. The hook measures *volume* (cheap, every turn); the
skill judges *substance* (rarely, conservatively). Refinement is never a
reason to touch a doc.
