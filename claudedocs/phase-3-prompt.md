# Phase 3 prompt — converge dev-report-framework onto the report-compose shell

Paste the prompt below into a fresh session in `agent-skills` when ready.
Prerequisites: Phases 1–2 are merged (report-compose `satellites` +
`page-link`, dev-report-framework `render_fragment_page.py`), and a real
release-report folder is available as test material (e.g.
`test/target_example.zip`).

---

We are converging `dev-report-framework` onto the `report-compose` shell so
both report genres share one design language and one presentation engine,
while dev-report-framework keeps sole ownership of the
`dev-report-fragment/v1` contract and all data rendering.

Work through these steps in order, verifying each in a browser before the
next:

1. **Extract the shared layer.** Promote what both skills already duplicate
   into repo-level `references/` (the repo rule: promote on the second
   consumer): the design token vocabulary and default theme (report-compose's
   `references/DESIGN.md` + `:root{}` block, dev-report-framework's
   `design-to-theme.md` — reconcile them into one token contract), the head
   contract (pinned CDN + SRI discipline, provenance meta, Google Fonts
   exemption), and the graceful-degradation rules. Update both skills to
   point at the shared layer; delete the superseded per-skill copies — no
   compatibility duplicates.

2. **Give dev-report-framework the report-compose navigation shell.** Replace
   the bespoke two-column release/vs-production chrome in
   `scripts/assets/index.html` + `app.js` with the report-compose engine's
   navigation model: categories as report-compose areas/tabs, fragments as
   menu items, the mode switcher (full/slides/xr) on the summary level.
   app.js keeps everything below the fragment level unchanged: the data
   island, all 11 section renderers, sortable/filterable tables, the module
   filter, split-screen previous-release comparison, and the file modal.
   Slides/xr modes operate on fragment summaries (title, status, metrics,
   metric-cards), not on full tables — a slide that would carry a 28,000-row
   table instead carries the fragment's headline numbers and a link to the
   full view.

3. **Make satellites the bridge in both directions.** dev-report-build gains
   a `--briefing` flag: after building the report folder, it emits a
   report-compose spec (reusing the summary-extraction logic from the
   fragments: manifest → areas/categories, fragment summaries + metrics →
   units, statuses → callouts/tiles) with `satellites` declared for every
   fragment whose payload exceeds the density rule, builds the briefing with
   report-compose's `build_report.py`, and fills each satellite with
   `render_fragment_page.py`. One command, one folder: `report.html` (the
   briefing, entry point) + `index.html` (the full app) + `<stem>-pages/`
   (filled satellites), all sharing the token layer.

4. **Verify end-to-end on the real release data** (unpack
   `test/target_example.zip`): the briefing opens standalone and passes
   `validate_output.py`; every page-link lands on a filled satellite; the
   full app opens with the new shell and keeps every existing capability
   (sort, filter, module filter, previous releases, file modal — check each);
   design tokens are visibly identical across all three surfaces; zero
   console errors everywhere.

5. **Documentation follows reality**: update both SKILL.md files and the
   shared references to describe the converged shape; remove every statement
   the convergence made false. Run the repo's authoring checklist on both
   skills before committing.

Constraints: do not weaken report-compose's single-file contract (satellites
stay its only exception); do not move fragment-schema knowledge into
report-compose; keep all scripts python3-stdlib; feature branch + PR, commit
per step.
