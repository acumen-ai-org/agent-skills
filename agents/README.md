# Shared Agents

Role definitions reused by **more than one** Skill. Empty by default — and
that is the correct default.

A role used by exactly one Skill belongs in that Skill's `references/`, not
here. Promote a role to this directory only when a second Skill genuinely
needs the same role; premature sharing recreates the coupling the
`references/` pattern exists to remove.

When you do add one, follow
[docs/authoring-agents.md](../docs/authoring-agents.md) (the "shared agent"
form, with frontmatter) and reference it from each consuming `SKILL.md`.

> Historical note: `content-to-image`'s three pipeline roles (`c2i-extract`,
> `c2i-art-direct`, `c2i-prompt-synth`) once lived here as registered private
> subagents. They were moved into `skills/content-to-image/references/` so the
> Skill is self-contained. See
> [docs/skills-vs-agents.md](../docs/skills-vs-agents.md#worked-example).
