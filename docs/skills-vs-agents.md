# Skills vs Agents

When to reach for a Skill, when for a subagent, and how they compose.

Sources: Anthropic *Skill authoring best practices*
(<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>)
and *Agents vs Skills: Quick Guide*
(<https://claudeblattman.com/downloads/agents-vs-skills-guide/>).

## Contents

- [The distinction](#the-distinction)
- [Decision guide](#decision-guide)
- [The better pattern](#the-better-pattern)
- [Worked example](#worked-example)
- [Host skill with internal producers](#host-skill-with-internal-producers)
- [Why not private skill agents](#why-not-private-skill-agents)

## The distinction

| | **Skill** | **Subagent** |
| --- | --- | --- |
| Runs in | Your main conversation, full context | An isolated context, fresh eyes |
| Best at | A portable, repeatable *workflow* | Separable work needing independence |
| Examples | "analyze this output", "generate this report", "follow this review checklist", "run this pipeline" | researcher, planner, implementer, reviewer, test fixer, security reviewer |
| Packaging | Multi-file bundle (`SKILL.md` + `references/` + `scripts/`) | A role definition the runtime can spawn |

A Skill is the unit of *reuse*. A subagent is the unit of *separation* — its
value is the fresh context that "avoids self-bias (won't rationalize its own
earlier choices)" (Blattman). The two are complementary: a Skill orchestrates;
when a step is separable it delegates to a role.

## Decision guide

```
Is it a reusable workflow you'll run again ("do this kind of thing")?
  └─ yes → Skill
Is it one separable job that benefits from a fresh, unbiased context
   (review, audit, an independent pipeline stage, parallel analysis)?
  └─ yes → a role the Skill delegates to
Is it a deterministic, fragile, must-be-identical-every-time step?
  └─ yes → a script in the Skill's scripts/
Is it a one-off, interactive, or needs the live conversation history?
  └─ yes → just do it in the main conversation; no Skill, no agent
```

The current trend is increasingly agentic — multiple concurrent
subagents for deeper autonomous work. That makes the *boundary* between a
Skill and the roles it delegates to the important design decision, not whether
to use agents at all.

## The better pattern

A Skill that delegates keeps the role **inside the Skill**, as a reference
file, and points at it from `SKILL.md`:

```
skills/<name>/
├── SKILL.md
├── references/
│   ├── reviewer-agent.md
│   └── planner-agent.md
└── scripts/
```

`SKILL.md` then says, in prose:

> For large changes, delegate review using the reviewer role described in
> `references/reviewer-agent.md`.

The runtime can run that role inline, or spawn it as an isolated agent using
the reference file as its instructions — you still get the fresh-context
benefit. What you avoid is a globally-registered private subagent that the
Skill silently depends on.

## Worked example

`skills/content-to-image/` is this pattern, refactored from the anti-pattern.

**Before** — the Skill depended on three privately-registered subagents:

```
agents/
├── CLAUDE.md            # 200-line authoring guide, repo-specific
├── c2i-extract.md       # registered subagent
├── c2i-art-direct.md    # registered subagent
└── c2i-prompt-synth.md  # registered subagent
skills/content-to-image/
└── SKILL.md             # "invoke c2i-extract via Agent tool, subagent_type: c2i-extract"
```

The Skill was not portable: drop `skills/content-to-image/` into another
project and it breaks, because `c2i-*` are not there. The 13-type taxonomy
tables and the 11-theme registry also bloated `SKILL.md`.

**After** — the Skill carries its own roles, detail, and scripts:

```
skills/content-to-image/
├── SKILL.md                 # concise; a table of contents
├── references/
│   ├── extract.md           # role (was agents/c2i-extract.md)
│   ├── art-direct.md        # role (was agents/c2i-art-direct.md)
│   ├── prompt-synth.md      # role (was agents/c2i-prompt-synth.md)
│   └── themes.md            # 11-theme registry pulled out of SKILL.md
└── scripts/
    ├── render.sh            # the curl call (was inline in SKILL.md §4)
    └── decode.py            # b64 → PNG (was inline in SKILL.md §5)
agents/                      # c2i-* removed; CLAUDE.md folded into docs/authoring-agents.md
```

`SKILL.md` now reads: *"Run the extract step following the role in
`references/extract.md` — inline, or as an isolated agent with that file as its
prompt."* The Skill is self-contained and portable; `SKILL.md` is short
because the taxonomy lives in the role files and the theme registry in
`references/themes.md` (progressive disclosure).

## Host skill with internal producers

The `references/`-role pattern scales to a whole pipeline.
`skills/dev-report-framework/` is one discoverable Skill that **bundles its
entire producer pipeline inside itself**. Each producer is a self-contained
bundle:

```
skills/dev-report-framework/
├── SKILL.md                       # the one discoverable entry point
├── references/  scripts/          # the host's own contract + validate/build
└── producers/
    ├── dev-analysis-architecture/
    │   ├── PRODUCER.md            # the producer workflow (not SKILL.md → not discovered)
    │   ├── references/            # its synthesis roles + detail
    │   └── scripts/               # its runners + to-fragment.py
    └── …                          # one bundle per question-producer
```

The entry file is `PRODUCER.md`, **not** `SKILL.md`, and it carries no `name:`
frontmatter — so skill discovery (which registers `skills/<name>/SKILL.md`)
cannot register it under any discovery behavior. The producers are invoked only
by the report pipeline; the host `SKILL.md` carries the roster and the
[invocation contract](../skills/dev-report-framework/SKILL.md#internal-producers).
This is the same "a role lives inside the Skill that uses it" rule as the
worked example — applied to a pipeline of a dozen roles instead of three.
A host bundle rather than a dozen top-level Skills because the producers answer
one composite question ("is this release safe to ship?"), are never invoked
independently, and a flat dozen `dev-*` entries would bury the skill index. The
placement rule for a producer is [dev-skill-taxonomy.md](dev-skill-taxonomy.md).

## Why not private skill agents

You *can* register per-Skill subagents. Avoid making that the core
abstraction:

- **Portability.** A registered subagent lives outside the Skill directory.
  Copy the Skill elsewhere and it silently breaks.
- **Discoverability.** A reference file sits next to the `SKILL.md` that uses
  it. A registered agent is action-at-a-distance.
- **Packaging.** Anthropic describes Skills as self-contained multi-file
  bundles. A Skill that needs external registration is not a bundle.
- **You keep the upside.** A role file can still be run as an isolated agent
  (pass it as the agent's instructions). You lose nothing by not registering.

Promote a role to a real shared agent in `/agents` only when a *second* Skill
needs the same role. See [authoring-agents.md](authoring-agents.md).
