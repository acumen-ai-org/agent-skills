# Authoring Agents and Roles

How to write the role definitions a Skill delegates to. A "role" and an
"agent" are the same content; the only difference is *where it lives and
whether the runtime registers it*:

| Form | Lives in | Registered? | Use when |
| --- | --- | --- | --- |
| **Reference role** | `skills/<name>/references/<role>.md` | No | Default. The role serves exactly one Skill. |
| **Shared agent** | `agents/<name>.md` | Yes (runtime-dependent) | A *second* Skill needs the same role. |

Decide between them with [skills-vs-agents.md](skills-vs-agents.md). Default to
a reference role — promote to a shared agent only on the second consumer.

## Contents

- [Reference roles](#reference-roles)
- [Shared agents](#shared-agents)
- [Frontmatter](#frontmatter)
- [Body — the system prompt](#body--the-system-prompt)
- [Minimal template](#minimal-template)
- [Checklist](#checklist)

## Reference roles

A reference role is a plain markdown doc — **no subagent frontmatter**
(`name`/`tools`/`model` are not needed; the Skill controls invocation). It
exists so `SKILL.md` can say "do step N following the role in
`references/<role>.md`". Structure it exactly like a system prompt (see
[Body](#body--the-system-prompt)). Optionally note a recommended model as
prose ("Recommended model: a mid-tier model — this is mechanical
transformation, not open-ended reasoning").

`skills/content-to-image/references/extract.md`, `art-direct.md`, and
`prompt-synth.md` are the canonical examples.

## Shared agents

A shared agent in `/agents` *may* be registered by the runtime (Claude Code
discovers `*.md` agent files and exposes them to the Agent tool). It carries
frontmatter so the runtime can route to it.

### Naming

`<category>-<purpose>`, lowercase letters and hyphens only — no uppercase,
digits, underscores, slashes, or spaces. The filename must match the `name`
field plus `.md`, and `name` must be unique. (These are hard runtime
constraints, not style.)

## Frontmatter

Registered agents require `name` and `description`. The runtime uses
`description` to decide whether to route work here, so write it as an
**imperative trigger**, not a generic summary: "Use this agent when reviewing
PRs that modify GraphQL schemas." — not "Reviews schemas."

Commonly useful optional fields:

| Field            | Purpose                                       | Example                  |
| ---------------- | --------------------------------------------- | ------------------------ |
| `tools`          | Restrict to a minimal tool list.              | `Read, Grep, Glob`       |
| `model`          | Pin a model. Defaults to inherit.             | `sonnet`                 |
| `color`          | UI chip color.                                | `blue`                   |
| `permissionMode` | Scope the permission surface.                 | `default`                |
| `maxTurns`       | Cap agentic turns.                            | `20`                     |
| `isolation`      | Run in a disposable git worktree.             | `worktree`               |

Reference roles use **none** of this — they are invoked by their owning Skill.

## Body — the system prompt

Good roles are **focused**: one role, one decision. Cover, in order:

1. **Role** — one sentence: what this is.
2. **When to invoke** — 2–3 concrete scenarios.
3. **Method** — numbered steps to follow.
4. **Output format** — exactly what it returns to the caller.
5. **Out of scope** — what it refuses or hands back.

Keep it tight. If the prompt bloats past ~80 lines of *instruction* (tables of
domain data don't count, but add a table of contents if the file passes 100
lines total — see [authoring-skills.md](authoring-skills.md#progressive-disclosure)),
the role is doing too much — split it.

## Minimal template

Reference role (no frontmatter):

```markdown
# <Role name>

Recommended model: <tier> — <one-line rationale>.

One sentence: what this role is.

## When invoked

- <concrete scenario>
- <concrete scenario>

## Method

1. <step>
2. <step>

## Output

<exactly what it returns — a strict template if the next step parses it>

## Out of scope

<what it refuses or hands back to the caller>
```

Registered shared agent — the same body, plus frontmatter:

```markdown
---
name: code-reviewer
description: Use when a change is ready for review and needs an independent
  pass for correctness, readability, and security.
tools: Read, Grep, Glob
model: sonnet
---

You are an independent code reviewer.
... (same five sections as above) ...
```

## Checklist

- [ ] Right home: one consumer → `references/`; two+ → `/agents`.
- [ ] Reference roles have **no** subagent frontmatter.
- [ ] Registered agents: filename == `name` + `.md`; `name` lowercase +
      hyphens, unique; `description` is an imperative trigger.
- [ ] Body covers role, when-to-invoke, method, output, out-of-scope.
- [ ] Output format is precise enough for the next step to consume verbatim.
- [ ] Focused — one role, one decision. Split if it sprawls.
- [ ] Table of contents if the file exceeds 100 lines.
