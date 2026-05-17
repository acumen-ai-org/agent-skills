# Repository Structure

How this repo is laid out and why. Conventions here are enforced in review.

## Contents

- [Tree](#tree)
- [Plugin & marketplace](#plugin--marketplace)
- [Skills](#skills)
- [Shared agents](#shared-agents)
- [Repo-level references, hooks, scripts](#repo-level-references-hooks-scripts)
- [Docs](#docs)
- [Ignored / runtime state](#ignored--runtime-state)
- [Naming conventions](#naming-conventions)
- [Adding a new Skill](#adding-a-new-skill)

## Tree

```
agent-skills/
├── .claude-plugin/
│   ├── plugin.json                 # this repo as a Claude Code plugin
│   └── marketplace.json            # single-plugin marketplace catalog
├── CLAUDE.md                       # agent entry point → /docs
├── README.md                       # human entry point
├── LICENSE                         # AGPLv3 (community use)
├── COMMERCIAL_LICENSE.md           # commercial/proprietary use terms
├── NOTICE                          # copyright + dual-license notice
├── .gitignore                      # ignores runtime state + build/OS noise
├── docs/
│   ├── README.md                   # docs index
│   ├── repository-structure.md     # this file
│   ├── skills-vs-agents.md         # decision guide + the "better pattern"
│   ├── authoring-skills.md         # SKILL.md best practices (Anthropic summary)
│   ├── authoring-agents.md         # agent/role authoring conventions
│   └── plugin-and-marketplace.md   # packaging/distribution as a CC plugin
├── skills/
│   ├── README.md                   # index of available Skills
│   └── content-to-image/
│       ├── SKILL.md                # the workflow (concise, < 500 lines)
│       ├── references/             # roles + detail, loaded on demand
│       │   ├── extract.md
│       │   ├── art-direct.md
│       │   ├── prompt-synth.md
│       │   └── themes.md
│       └── scripts/                # deterministic steps, executed not read
│           ├── render.sh
│           └── decode.py
├── agents/
│   └── README.md                   # roles shared by 2+ Skills (skeleton)
├── references/                     # repo-level shared references  (empty until needed *)
├── hooks/                          # session/agent lifecycle hooks (empty until needed *)
└── scripts/                        # repo-level maintenance scripts (empty until needed *)
```

`*` Git does not store empty directories, so these three are **not
version-controlled until they contain a file**. They are conventional
locations: create the directory when you have its first occupant (see
[Repo-level references, hooks, scripts](#repo-level-references-hooks-scripts)).
A fresh clone will not contain them — that is expected.

## Plugin & marketplace

`.claude-plugin/` holds the two manifests that make this repo installable as a
Claude Code plugin:

- `plugin.json` — the plugin manifest (name `agent-skills`, metadata,
  dual-license SPDX expression). Components are auto-discovered from `skills/`
  and `agents/` at the repo root, so no component paths are declared.
- `marketplace.json` — a single-plugin catalog (marketplace name
  `acumen-agent-skills`; the plugin's `source` is `"./"`, the repo root).

Only the manifests live in `.claude-plugin/` — component dirs (`skills/`,
`agents/`, `hooks/`) stay at the repo root, which is also the plugin root.
The marketplace is **not** named `agent-skills`: that name is reserved for
Anthropic. Full detail, schemas, install/test/version commands, and the
upstream doc citations are in
[plugin-and-marketplace.md](plugin-and-marketplace.md).

## Skills

Each Skill is **one directory** under `skills/` containing a `SKILL.md`. That
directory is the entire Skill — it carries everything it needs:

- `SKILL.md` — the workflow. Concise. A table of contents that points into
  `references/` and `scripts/`. Under 500 lines.
- `references/` — role definitions and reference material the Skill loads
  *only when needed*. One level deep from `SKILL.md`.
- `scripts/` — deterministic, error-prone, or must-be-consistent steps.
  Executed by the agent, not pasted into context.

A Skill never depends on anything outside its own directory except shared
roles in `/agents`. It must never depend on a privately-registered subagent —
that coupling is exactly what the `references/` pattern removes. See
[skills-vs-agents.md](skills-vs-agents.md).

## Shared agents

`/agents` holds role definitions reused by **more than one** Skill (e.g. a
generic `code-reviewer`). A role used by exactly one Skill belongs in that
Skill's `references/`, not here. Promote a role to `/agents` only when a second
Skill genuinely needs it — premature sharing creates coupling.

## Repo-level references, hooks, scripts

Three top-level directories mirror the per-Skill folders but operate at
**repo scope**. They start empty and stay out of git until they have a first
occupant (git does not track empty directories). Create the directory when —
and only when — you have something that belongs in it. The rule is the same as
`/agents`: do not pre-populate; promote on the second consumer.

| Dir          | Holds                                                                 | Promote here when…                                                              | Distinct from                                                                 |
| ------------ | --------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `references/` | Reference material (checklists, schemas, patterns) used by 2+ Skills. | A second Skill needs the same reference doc that currently lives in one Skill's `references/`. | `skills/<name>/references/` — material scoped to a single Skill.               |
| `hooks/`      | Session / agent lifecycle hooks the runtime executes (e.g. `SessionStart`, `SubagentStart`/`Stop`). | You need automation that runs *around* Skills/agents rather than inside one — logging, runtime-state files, attribution. | A `SKILL.md` step — hooks are runtime glue, not part of any one workflow.      |
| `scripts/`    | Repo-level maintenance/CI scripts (lint a `SKILL.md`, validate the tree, regenerate an index). | A script operates on the **repository**, not on a Skill's task data.            | `skills/<name>/scripts/` — deterministic steps a single Skill executes.        |

When you do populate one:

1. `mkdir references` (or `hooks` / `scripts`) and add the file — the first
   commit that adds a file is what puts the directory in git.
2. Name files descriptively and follow the same conventions as their per-Skill
   counterparts ([Naming conventions](#naming-conventions)).
3. For `hooks/`, the runtime state it writes (status files, logs) is
   **ignored**, not committed — see [Ignored / runtime state](#ignored--runtime-state)
   and the runtime contract in
   [authoring-agents.md](authoring-agents.md).
4. Reference the new file from whatever consumes it (a `SKILL.md`, another
   doc) so it is discoverable rather than action-at-a-distance.

## Docs

`/docs` is reference material for authors, not loaded by Skills at runtime.
Keep each doc focused on one concern and cross-link rather than duplicate.

## Ignored / runtime state

`.gitignore` keeps generated and machine-local files out of git:

- **Build/byte-compile artifacts** — `__pycache__/`, `*.pyc` (e.g. from
  byte-compiling a skill script).
- **Agent/skill runtime state** — `.agents/`, `**/logs/`, `**/status.json`.
  Hooks write these at run time; they are per-run, never committed.
- **Local env / secrets** — `.env*` (except `.env.example`).
- **OS and editor noise** — `.DS_Store`, `.idea/`, `.vscode/`, swap files.

The empty skeleton dirs (`references/`, `hooks/`, `scripts/`) are *not*
`.gitignore`d — they are simply absent until they hold a file. There is no
`.gitkeep`: keeping them empty-and-untracked is intentional, so the tree
reflects what actually exists.

## Naming conventions

| Thing            | Rule                                                                 |
| ---------------- | -------------------------------------------------------------------- |
| Skill directory  | lowercase, hyphens; matches the `name:` in its `SKILL.md`.           |
| Skill `name`     | ≤ 64 chars, `[a-z0-9-]` only, no `anthropic`/`claude`. Prefer gerund (`processing-pdfs`) or noun phrase (`content-to-image`). |
| Reference file   | Describes its content: `art-direct.md`, not `doc2.md`.               |
| Script           | Verb-first: `render.sh`, `decode.py`. Forward slashes everywhere.    |
| Shared agent     | `<category>-<purpose>.md`, lowercase + hyphens (see authoring-agents). |

## Adding a new Skill

1. `mkdir -p skills/<name>/{references,scripts}`.
2. Write `SKILL.md` with `name` + `description` frontmatter. Follow
   [authoring-skills.md](authoring-skills.md).
3. Put any role you delegate to in `references/<role>.md`.
4. Put deterministic steps in `scripts/`.
5. Add the Skill to `skills/README.md`.
6. Self-review against the checklist in
   [authoring-skills.md](authoring-skills.md#checklist).
