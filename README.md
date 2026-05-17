# agent-skills

A collection of reusable agent **Skills** — portable, repeatable workflows that
any Claude Code (or compatible) session can discover and run.

Inspired by the structure of
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills).

## Licensing

This project is **dual-licensed**:

- **Community use** is available under the GNU Affero General Public License
  v3.0 — see [LICENSE](LICENSE).
- **Commercial, proprietary, closed-source, SaaS, hosted, or internal business
  use** requires a separate written commercial agreement — see
  [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

Use without a signed commercial agreement is governed solely by the AGPLv3,
including its source-availability and network-use obligations. To obtain a
commercial license, contact **fredrik@acumen-ai.org**.

## Quick start

1. Point your agent at this repo (or symlink `skills/` into your project).
2. The agent loads each Skill's `name` + `description` at startup.
3. When a request matches, the agent reads that Skill's `SKILL.md` and follows
   it — pulling in `references/` and `scripts/` only as needed.

## Layout

```
agent-skills/
├── CLAUDE.md                 # entry point for agents working in this repo
├── README.md                 # this file
├── LICENSE                   # AGPLv3 (community use)
├── COMMERCIAL_LICENSE.md     # commercial/proprietary use terms
├── NOTICE                    # copyright + dual-license notice
├── .gitignore                # ignores runtime state + build/OS noise
├── docs/                     # how to author + how the repo is structured
├── skills/
│   └── content-to-image/     # a Skill: SKILL.md + references/ + scripts/
├── agents/                   # roles shared across more than one Skill
├── references/               # repo-level shared references  (empty until needed)
├── hooks/                    # session/agent lifecycle hooks (empty until needed)
└── scripts/                  # repo-level maintenance scripts (empty until needed)
```

`references/`, `hooks/`, and `scripts/` are conventional repo-level locations.
They start empty, so git does not track them until they hold a file — create
each on first use. See
[docs/repository-structure.md](docs/repository-structure.md#repo-level-references-hooks-scripts).

## Authoring

Start at [docs/README.md](docs/README.md). The non-negotiables:

- A Skill is **self-contained**. No Skill depends on a privately-registered
  subagent; per-Skill roles live in `skills/<name>/references/`.
- `SKILL.md` is concise (< 500 lines) and uses progressive disclosure.
- Deterministic, fragile steps are `scripts/`, not prose.

See [docs/skills-vs-agents.md](docs/skills-vs-agents.md) for when to reach for a
Skill vs a subagent, and [docs/authoring-skills.md](docs/authoring-skills.md)
for the full checklist.
