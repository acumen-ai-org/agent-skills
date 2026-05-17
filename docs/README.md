# Documentation Index

Authoring and structure guidance for this repository. Start here.

| Doc                                                  | Read it when…                                                              |
| ---------------------------------------------------- | -------------------------------------------------------------------------- |
| [repository-structure.md](repository-structure.md)   | You want the directory layout and naming conventions.                      |
| [skills-vs-agents.md](skills-vs-agents.md)           | You're deciding whether something is a Skill, a subagent, or a role file.  |
| [authoring-skills.md](authoring-skills.md)           | You're writing or reviewing a `SKILL.md`.                                   |
| [authoring-agents.md](authoring-agents.md)           | You're writing an agent/role definition (registered subagent or role doc). |
| [plugin-and-marketplace.md](plugin-and-marketplace.md) | You're packaging, testing, installing, or versioning this repo as a Claude Code plugin/marketplace. |
| [dev-tooling-catalog.md](dev-tooling-catalog.md)     | You want the OSS analysis/reporting tools available and which Skill owns each.                      |
| [dev-skill-taxonomy.md](dev-skill-taxonomy.md)       | You're placing a new dev-tooling tool (the `dev-analysis-`/`dev-test-`/`dev-report-` rule).         |
| [dev-report-framework.md](dev-report-framework.md)   | You're producing or consuming report fragments, or building the standalone HTML report.            |
| [tools_implementation.md](tools_implementation.md)   | You're implementing the dev-tooling Skills (the ordered build backlog).                             |

## Sources

These docs summarize and adapt two upstream references. Read the originals when
you need the full detail:

- Anthropic — *Skill authoring best practices*:
  <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- *Agents vs Skills: Quick Guide* (Blattman):
  <https://claudeblattman.com/downloads/agents-vs-skills-guide/>

Each doc cites which source a recommendation comes from so you can trace it
back. When upstream guidance and a doc here disagree, the upstream source wins —
open a PR to fix the doc.

## The one pattern to internalize

A Skill is self-contained. Roles it delegates to live in its own
`references/` folder, not as globally-registered private subagents:

```
skills/<name>/
├── SKILL.md            # the workflow; a table of contents
├── references/
│   ├── <role>.md       # "delegate X using the role described here"
│   └── <topic>.md      # detail pulled out of SKILL.md for progressive disclosure
└── scripts/
    └── <step>.sh|.py   # deterministic, fragile steps — executed, not described
```

`skills/content-to-image/` is the worked example. It was refactored *from* the
anti-pattern (three private `c2i-*` subagents in a top-level `agents/`) *to*
this pattern. See [skills-vs-agents.md](skills-vs-agents.md#worked-example) for
the before/after.
