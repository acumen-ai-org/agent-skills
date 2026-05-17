# Plugin & Marketplace

This repository is **both** a Claude Code plugin and a single-plugin
marketplace that distributes it. This doc explains the setup, the manifests,
and how to test, install, and version it.

Sources (authoritative — read these when the schema matters):

- Create plugins: <https://code.claude.com/docs/en/plugins>
- Plugin marketplaces: <https://code.claude.com/docs/en/plugin-marketplaces>
- Plugins reference (full schema): <https://code.claude.com/docs/en/plugins-reference>
- Discover & install: <https://code.claude.com/docs/en/discover-plugins>

## Contents

- [Identity](#identity)
- [Why the marketplace is not named `agent-skills`](#why-the-marketplace-is-not-named-agent-skills)
- [File layout](#file-layout)
- [plugin.json](#pluginjson)
- [marketplace.json](#marketplacejson)
- [Test locally](#test-locally)
- [Install from the marketplace](#install-from-the-marketplace)
- [Versioning](#versioning)
- [Licensing inside the plugin](#licensing-inside-the-plugin)
- [Known limitation: skill script paths](#known-limitation-skill-script-paths)

## Identity

| Thing            | Value                                  | Notes                                                                 |
| ---------------- | -------------------------------------- | --------------------------------------------------------------------- |
| Plugin name      | `agent-skills`                         | Namespaces skills: `content-to-image` → `/agent-skills:content-to-image`. |
| Marketplace name | `acumen-agent-skills`                  | Public-facing in `/plugin install <plugin>@<marketplace>`.            |
| Owner            | Acumen AI Pty Ltd · fredrik@acumen-ai.org | Marketplace maintainer.                                            |
| Source           | This repo (`acumen-ai-org/agent-skills`) | Plugin `source` is `"./"` — marketplace root *is* the plugin root.  |

The repo root is the plugin root: Claude Code auto-discovers `skills/` (and
`agents/` once populated) from there. Only the two manifests live in
`.claude-plugin/`.

## Why the marketplace is not named `agent-skills`

The official docs list `agent-skills` among marketplace names **reserved for
Anthropic** that third-party marketplaces cannot use (see
[plugin-marketplaces](https://code.claude.com/docs/en/plugin-marketplaces),
"Reserved names"). Names that impersonate official marketplaces are also
blocked. The marketplace is therefore `acumen-agent-skills` (owner-prefixed,
non-impersonating). The *plugin* name `agent-skills` is fine — only
*marketplace* names are reserved.

## File layout

```
agent-skills/                       # plugin root  AND  marketplace root
├── .claude-plugin/
│   ├── plugin.json                 # plugin manifest
│   └── marketplace.json            # marketplace catalog (lists this one plugin)
├── skills/
│   └── content-to-image/SKILL.md   # auto-discovered (no manifest entry needed)
└── agents/                         # auto-discovered when it holds agent .md files
```

Per the official "Common mistake" warning: component directories (`skills/`,
`agents/`, `hooks/`) live at the **plugin root**, never inside
`.claude-plugin/`. Only the manifests go in `.claude-plugin/`.

## plugin.json

`.claude-plugin/plugin.json`. The manifest is optional (components auto-discover
from default locations and the name would derive from the directory); we
include it for metadata and the namespace.

- **Required:** `name` (kebab-case, no spaces).
- **We set:** `$schema` (editor validation only — ignored at load),
  `version`, `description`, `author` (object: `name`, `email`, `url`),
  `homepage`, `repository`, `license`, `keywords`.
- **We do not set component paths** (`skills`, `agents`, `hooks`, …): the
  default locations already match this repo, so overrides would be noise.
- `${CLAUDE_PLUGIN_ROOT}` is available to hook/MCP commands if we add them
  later; it resolves to the installed plugin's root.

## marketplace.json

`.claude-plugin/marketplace.json`.

- **Required:** `name`, `owner` (object — `name` required, `email` optional),
  `plugins` (array).
- Each plugin entry **requires** `name` and `source`. `source: "./"` means the
  plugin is at the marketplace root (this repo) — a string source must match
  `^\./.*` (start with `./`), so `"."` is rejected by the schema. Relative-path
  sources only
  resolve when users add the marketplace **via git** (the case here — see
  below); for URL-based distribution a `github`/`url`/`git` source object
  would be required instead.
- Plugin entries may also carry manifest fields (`description`, `license`,
  `category`, `keywords`, …). When both are present, `plugin.json` is the
  authority for component definitions (`strict` defaults to true).

## Test locally

No install needed during development:

```bash
claude --plugin-dir .
```

Then exercise the skill (`/agent-skills:content-to-image`) and run
`/reload-plugins` after edits. Validate the manifests with the CLI when
available:

```bash
claude plugin validate .
```

## Install from the marketplace

Users add the marketplace (via the GitHub repo, which makes the `"./"`
relative source resolve), then install the plugin:

```text
/plugin marketplace add https://github.com/acumen-ai-org/agent-skills
/plugin install agent-skills@acumen-agent-skills
```

To pin scope (team vs personal), see the install-scope table in the
[plugins reference](https://code.claude.com/docs/en/plugins-reference). Updates:
`/plugin marketplace update acumen-agent-skills`.

## Versioning

`version` in `plugin.json` is set, so the plugin is **pinned** to that string
— installed users only receive updates when it changes. (If `version` were
omitted and distributed via git, every commit SHA would instead count as a new
version.) The marketplace entry intentionally omits `version` to avoid a
second source of truth; `plugin.json` wins on conflict.

Bumping is **automated** by a tracked pre-commit hook
(`.githooks/pre-commit`): every commit increments the minor under a `0.x.0`
scheme (`0.2.0` → `0.3.0` …) and stages `plugin.json` into that same commit.
It is pre-commit (not post-commit / pre-push + `--amend`) on purpose — amend
re-fires hooks and rewrites/​diverges already-finalized commits.

Opt in **once per clone**:

```bash
git config core.hooksPath .githooks
```

Accepted trade-offs (chosen over omitting `version`): the number is a commit
counter, not a semantic release marker; **every** commit bumps it (WIP, docs,
merges); `git commit --amend`, rebase, and cherry-pick replays bump again; and
the version line is a recurring cross-branch merge-conflict point. If a clone
has not opted in, nothing bumps and the last committed `version` stands.

## Licensing inside the plugin

The `license` field is the SPDX expression
`AGPL-3.0-only OR LicenseRef-Commercial`, reflecting this project's dual
license. Installing or distributing the plugin without a signed commercial
agreement is governed solely by the AGPLv3 — including its
source-availability and network-use obligations. See
[../LICENSE](../LICENSE), [../COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md),
and the [Licensing section of the README](../README.md#licensing).

## Skill script paths

Skills must invoke bundled scripts via **`${CLAUDE_SKILL_DIR}`**, the directory
containing that skill's `SKILL.md`:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/render.sh" <args>
python3 "${CLAUDE_SKILL_DIR}/scripts/decode.py" <args>
```

Claude Code substitutes `${CLAUDE_SKILL_DIR}` inline into skill content before
the model sees it, so the path resolves regardless of working directory and
after marketplace install (the skill dir is copied into the plugin cache).
`content-to-image` uses this.

Do **not** use `${CLAUDE_PLUGIN_ROOT}` for this. It is substituted in
plugin.json / hook / MCP / LSP configs and exported only to hook and MCP/LSP
*subprocesses* — it is **not** an env var available to Bash commands the model
runs from a skill, so `bash $CLAUDE_PLUGIN_ROOT/...` inside a skill step would
break. Relative paths (`bash scripts/render.sh`) also break once installed,
because the working directory is then the user's project, not the skill dir.
