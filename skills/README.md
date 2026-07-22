# Skills

Each subdirectory is one self-contained Skill: a `SKILL.md` plus its
`references/` and `scripts/`. The agent loads each Skill's `name` +
`description` at startup and reads the rest only when a request matches.

## Available Skills

| Skill | Description |
| --- | --- |
| [content-to-image](content-to-image/SKILL.md) | Convert a piece of text into a single explanatory illustration via a 3-step pipeline (extract → art-direct → prompt-synth), then render with Gemini (default), gpt-image on Azure Foundry, or the OpenAI API. |
| [dev-release-candidate](dev-release-candidate/SKILL.md) | Build a release candidate driven by dev-process.json: branch from origin/main, compute the main↔production scope, run configured analysis/review tools in parallel (heavy ones as sub-agents), optionally generate changelog/notes and an aggregated viewer, and make the release-candidate commit. Informs about the freeze/notify/push steps it does not perform. |
| [dev-release-publish](dev-release-publish/SKILL.md) | Finalize a verified release candidate: rewrite the release-candidate commit so report artifacts go to AWS S3 / Azure Blob instead of git history while configured reports stay committed. Informs about the approval/production-release/notify steps it does not perform. |
| [sys-sync](sys-sync/SKILL.md) | Conservative docs/report synchronizer for opted-in repos: after considerable changes (Stop-hook triggered), updates in-place reports and required docs only when their statements became false; always advances the sync point. |
| [sys-init](sys-init/SKILL.md) | Adopts the Acumen ways of working in a repo: sys.json, CLAUDE.md pointer block, .ai gitignore, first doc-coverage check. |
| [report-compose](report-compose/SKILL.md) | Generates one self-contained HTML file with all three view modes baked in — full report, slide deck, and XR glasses-UI — selected by `?mode=` and switchable at runtime; three-level navigation (Areas/Categories/Menu items) with gateway slides, a controls registry (Plot, diff, Excalidraw, sparklines, Mermaid), optional DESIGN.md theming over an oakai-style default. Two-role pipeline: a content role authors a spec directory, a fast-model structure role assembles and validates it with deterministic build/validate scripts. |
| [dev-report-framework](dev-report-framework/SKILL.md) | The release-report system. Aggregates the JSON fragments produced by its **bundled internal producers** into one standalone HTML "Release candidate report" per release: two-column This-release / vs-production layout, producer-declared per-part top menu, in-place file/markdown preview, show/hide previous releases, a global `Module:` filter (from `dev-process.json` `modules`), optional DESIGN.md theming. Owns the fragment JSON contract, `validate_fragments.py`, `dev-report-build`, and the internal producers under `producers/`. |

## Internal producers

The dev-analysis / dev-test / dev-report **producers** are not standalone
skills. They are bundled inside `dev-report-framework` at
`dev-report-framework/producers/<name>/PRODUCER.md` (each with its own
`references/` and `scripts/`) and are invoked only by the report pipeline —
never directly by a user or consumer. See
[dev-report-framework → Internal producers](dev-report-framework/SKILL.md#internal-producers)
for the roster and invocation contract, and
[docs/dev-skill-taxonomy.md](../docs/dev-skill-taxonomy.md) for how a producer
is placed.

## Adding a Skill

See [docs/repository-structure.md](../docs/repository-structure.md#adding-a-new-skill)
and the checklist in [docs/authoring-skills.md](../docs/authoring-skills.md#checklist).
Add a row to the table above when you do.

A Skill is self-contained: roles it delegates to live in its own
`references/`, never as a globally-registered private subagent. See
[docs/skills-vs-agents.md](../docs/skills-vs-agents.md).
