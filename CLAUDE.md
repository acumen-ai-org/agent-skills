# Agent Skills — Repository Guide

This repository packages reusable agent capabilities as **Skills** and the
**roles** they delegate to. This file is the entry point. The substance lives
in `/docs` — keep this file short and route from here.

## Hard rules

- Do not add comments to code.
- Zero comments unless explicitly requested.
- If a comment is added, treat it as a failure and regenerate.

### Code lifecycle — delete, don't preserve

When you change something, change it everywhere and remove the old shape. The codebase reflects what the system **is**, not what it used to be — git history covers the rest.

Things we don't keep around:

- **Backward-compat shims** — deprecated re-exports, dual code paths "until callers migrate", old signatures kept alongside new ones. Migrate the callers in the same change and drop the old shape.
- **Commented-out code.** Use `git log` and `git blame` to recover anything you need.
- **"Just in case" branches, fields, or files** that aren't reachable from any current callsite. Unreachable today = unreachable forever (until someone deletes it in a year, harder).
- **Stuck-on feature flags.** Once a flag is fully rolled out, delete the flag and the unused branch in the same commit.
- **Renamed-but-kept aliases.** If `foo` is now `bar`, delete `foo`. Don't export both.
- **Defensive paths for "scenarios that can't happen"** at internal boundaries — validate at system edges only.

Every line you preserve has to be read, understood, and ruled out by the next person debugging. If a piece of code earns its keep today, it stays; otherwise it goes.

### Documentation voice — describe reality, not the journey

Docs describe the system as it **is** — or, for forward-looking docs (specs, ADRs, target architecture), as we want it to **be**. They are not a changelog, a status report, or a narrative of who did what.

Don't write:

- **"We've done X"**, **"recently changed"**, **"as part of this work"**, **"the changes made are…"** — past-tense or workflow framing. Release notes and git history are where that lives.
- **"Currently we're migrating to…"**, **"in progress"**, **"WIP"**, **"TODO: finish this section"** — ongoing-work framing. Either the new shape is real (document that) or it isn't (don't document it yet).
- **"Previously this used X, now it uses Y"** — leave only the Y. The old shape is gone; the doc should be too.
- **"This PR adds…"**, **"this change introduces…"** — PR-flavored prose in a doc that will outlive the PR by years.

Write the doc as if a new engineer is reading it cold, with no knowledge of what changed last week. State what the system does, what the contract is, why it's shaped that way. If you're tempted to write "now" or "currently", delete the word and re-read — the sentence is almost always stronger without it.

## What lives where

| Path             | Holds                                                                   |
| ---------------- | ----------------------------------------------------------------------- |
| `skills/<name>/` | One self-contained Skill: `SKILL.md` + `references/` + `scripts/`.      |
| `agents/`        | Shared agent roles reused across more than one Skill.                   |
| `docs/`          | How to author Skills/agents and how the repo is structured.             |
| `references/`    | Repo-level reference material shared by 2+ Skills. Empty until needed.  |
| `hooks/`         | Session/agent lifecycle hooks the runtime executes. Empty until needed. |
| `scripts/`       | Repo-level maintenance/CI scripts. Empty until needed.                  |

`references/`, `hooks/`, `scripts/` start empty and are not version-controlled
until they hold a file (git does not track empty dirs). They are conventional
locations — create the dir on first use, promote on the second consumer (same
rule as `agents/`). Detail:
[docs/repository-structure.md](docs/repository-structure.md#repo-level-references-hooks-scripts).

## Read these before authoring

| If you are…                      | Read                                                         |
| -------------------------------- | ------------------------------------------------------------ |
| New to the repo                  | [docs/repository-structure.md](docs/repository-structure.md) |
| Deciding Skill vs subagent       | [docs/skills-vs-agents.md](docs/skills-vs-agents.md)         |
| Writing or editing a `SKILL.md`  | [docs/authoring-skills.md](docs/authoring-skills.md)         |
| Writing an agent/role definition | [docs/authoring-agents.md](docs/authoring-agents.md)         |

Full index: [docs/README.md](docs/README.md).

## Golden rules

1. **A Skill is a portable, repeatable workflow.** It is self-contained: a
   Skill never depends on a globally-registered private subagent. Per-Skill
   roles live in that Skill's `references/`.
2. **Delegate separable work to roles.** When a step benefits from fresh
   context (review, audit, an independent pipeline stage), the `SKILL.md`
   points at a role file in `references/` and may run it as an isolated agent.
3. **Progressive disclosure.** `SKILL.md` is a table of contents. Push detail
   into `references/` (one level deep) and deterministic steps into `scripts/`.
4. **Earn every token.** Assume the model is already capable. Add only what it
   does not already know. Keep `SKILL.md` under 500 lines.

The worked example of all four rules is `skills/content-to-image/`.
