# Skills

Each subdirectory is one self-contained Skill: a `SKILL.md` plus its
`references/` and `scripts/`. The agent loads each Skill's `name` +
`description` at startup and reads the rest only when a request matches.

## Available Skills

| Skill | Description |
| --- | --- |
| [content-to-image](content-to-image/SKILL.md) | Convert a piece of text into a single explanatory illustration via a 3-step pipeline (extract → art-direct → prompt-synth), then render with gpt-image (Azure Foundry or the OpenAI API). |

## Adding a Skill

See [docs/repository-structure.md](../docs/repository-structure.md#adding-a-new-skill)
and the checklist in [docs/authoring-skills.md](../docs/authoring-skills.md#checklist).
Add a row to the table above when you do.

A Skill is self-contained: roles it delegates to live in its own
`references/`, never as a globally-registered private subagent. See
[docs/skills-vs-agents.md](../docs/skills-vs-agents.md).
