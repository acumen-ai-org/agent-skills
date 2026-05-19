# dev-process.json — configuration contract

The release process is driven by `dev-process.json` at the consuming
repository root. This file is the field-by-field contract. The JSON Schema
ships bundled with the plugin (the file
[`dev-process.schema.json`](dev-process.schema.json) next to this document);
`python3 scripts/dev_process.py schema` prints it on demand. Validation
(`check`/`emit`) always uses the bundled schema.

The skills perform only part of the release process and **inform** about the
external steps (merge freeze, notify, push, production release, merge-back).
This config covers the parts the skills act on plus the report/blob behavior.

## Contents

- [Bootstrap & validation](#bootstrap--validation)
- [Variable substitution](#variable-substitution)
- [Top-level keys](#top-level-keys)
  - [branches](#branches)
  - [scope](#scope)
  - [analysis & review (the tool shape)](#analysis--review-the-tool-shape)
  - [reports](#reports)
  - [releaseNotes](#releasenotes)
  - [blob](#blob)
  - [modules](#modules)
- [Blob storage credentials](#blob-storage-credentials)
- [gitignore the report dir](#gitignore-the-report-dir)

## Bootstrap & validation

- `python3 scripts/dev_process.py init` — if `dev-process.json` is absent,
  writes a documented default, then validates. It never auto-commits; the
  operator reviews and commits it. If the file exists, `init` only validates.
- `python3 scripts/dev_process.py check` — validate only. Exit `0` valid,
  `2` invalid (each error printed with its JSON path), `1` bad usage.
- `python3 scripts/dev_process.py emit` — validate, then print the config with
  all `${...}` resolved. Every other script consumes `emit`, so an invalid
  config fails fast and uniformly.
- `python3 scripts/dev_process.py value <release-candidate-branch|release-id>` —
  the release candidate branch name / release id, single-sourced for the shell
  scripts.

The default is deliberately inert: `blob.provider: "none"`, no configured
analysis/review tools beyond a no-op sample. A fresh repo runs the skill's
steps without touching any external system. `additionalProperties` is `false`
everywhere, so a typo'd key is a validation error, not a silently ignored
field.

## Variable substitution

`emit` resolves `${...}` tokens in any string value, repeatedly until stable:

- `${main}`, `${production}` — the branch names from `branches`.
- `${branches.releaseCandidate}` / `${releaseCandidateBranch}` — the release
  candidate branch name.
- `${releaseId}` — `DEV_RELEASE_ID` if set, else `<UTCdate>-<short HEAD sha>`.
- Any dotted path into the config, e.g. `${scope.range}`, `${branches.main}`.

## Top-level keys

### branches

| Field | Default | Meaning |
| --- | --- | --- |
| `main` | `main` | Integration branch. The release candidate branch is created from `origin/<main>`. |
| `production` | `production` | The released branch — the state in production. The "released" side of the scope range. |
| `releaseCandidate` | `release-candidate` | Release candidate branch name. In practice it is just `origin/main` at branch time. |

### scope

| Field | Default | Meaning |
| --- | --- | --- |
| `range` | `${production}..${main}` | Git range template for the release scope. |
| `productionRef.strategy` | `branch` | How to resolve the released endpoint: `branch` → `origin/<production>`; `tag` → latest tag matching `tagPattern`; `commit` → explicit SHA. |
| `productionRef.tagPattern` | `v*` | Glob for the `tag` strategy. |
| `productionRef.commit` | `null` | Explicit SHA for the `commit` strategy. |
| `fallbackOrder` | `["branch","tag","root"]` | Tried in order if the primary endpoint is unresolvable. `root` = first commit (whole history; emits a warning). |
| `changedFilesPathspec` | `[]` | Optional pathspec restricting the changed-file list. |

`scope.sh` writes `scope.json` (`from`, `to`, `range`, `endpointStrategy`,
`commitCount`), `commits.txt`, and `changed-files.txt` into
`reports.outputDir`.

### analysis & review (the tool shape)

`analysis` and `review` are arrays of the same `tool` object. They are
separated only so the summary groups them. Each entry:

| Field | Default | Meaning |
| --- | --- | --- |
| `id` | — (required) | Slug `^[a-z0-9][a-z0-9-]*$`; report file is `<id>.<ext>`. |
| `title` | `id` | Human label in the summary. |
| `kind` | — (required) | `command` (shell) or `skill` (a skill/agent invoked as an isolated sub-agent). |
| `run` | — (required) | The shell command, or the skill/agent name/instruction. |
| `args` | `{}` | Passed to a skill entry; `${...}` is resolved. |
| `report.format` | `markdown` | `text`/`markdown`/`html`/`json`/`sarif` — picks the report extension. |
| `heavy` | `kind=="skill"` | `true` → always run as an isolated sub-agent. |
| `parallelizable` | `true` | Informational; the orchestrator batches all entries. |
| `blocking` | `false` | `true` → a non-zero exit fails the gate (unless `advisory`). |
| `advisory` | `false` | `true` → failures are recorded but never block the gate. |
| `timeoutSeconds` | `1800` | Per-entry timeout. |
| `enabled` | `true` | `false` → skipped entirely. |

An empty `analysis` + `review` is valid: the gate passes and a valid release
candidate is still produced. Adding analysis later is a config change (a new
entry), not an orchestrator change — that is the phase-1/phase-2 seam.

A `kind:"skill"` `run` naming one of the eight first-party producers
(`dev-analysis-*`, `dev-test-contracts`) is resolved to that producer's
bundled internal path and run for you; any other `run` is dispatched verbatim
as your own command/agent. To add **your own** producer — recommended layout,
the fragment + validator + fixed-`category` contract it must honor, and the
wiring — see
[Adding your own producer (consuming repos)](../../../docs/dev-report-framework.md#adding-your-own-producer-consuming-repos).

### reports

| Field | Default | Meaning |
| --- | --- | --- |
| `outputDir` | `.agents/release-reports` | Per-tool reports + scope artifacts + gate files. Should be gitignored. |
| `viewerPath` | `.agents/release-reports/index.html` | Where a configured aggregator should write the combined viewer. |
| `persistInRepo` | `none` | What the publish finalize step keeps in the (amended) release-candidate commit: `all` = every report; `none` = nothing; `except-media` = non-media reports only. The rest goes to blob. |
| `mediaExtensions` | `.png,.jpg,...` | Extensions treated as media for `except-media`. |
| `persistPath` | `release-reports` | In-repo destination for kept reports (distinct from the gitignored `outputDir`). |
| `aggregate.kind` / `aggregate.run` | `command` / `null` | Optional report aggregator. `null` → C3 is skipped. |
| `designDoc` | `null` | Optional path (relative to repo root) to a DESIGN.md whose contents shape the generated report's look-and-feel. `null`/absent → default theme. |

### releaseNotes

| Field | Default | Meaning |
| --- | --- | --- |
| `path` | `RELEASE_NOTES.md` | Release-notes output path. |
| `changelogPath` | `CHANGELOG.md` | Changelog output path. |
| `sources` | `["commits","PRs"]` | Inputs a generator should use. |
| `changelogMode` | `prepend` | `prepend` or `overwrite`. |
| `commitSubjectFilter` | `null` | Optional regex limiting which commit subjects feed the changelog. |
| `generate.kind` / `generate.run` | `command` / `null` | Optional notes/changelog generator. `null` → C2 is skipped (first-party generator is phase two). |

### blob

| Field | Default | Meaning |
| --- | --- | --- |
| `provider` | `none` | `none` (never upload — reports are discarded after the commit is finalized unless `persistInRepo` keeps them), `aws` (S3), or `azure` (Azure Blob). |
| `prefix` | `releases/${releaseId}` | Destination key prefix; `${...}` resolved. |

The publish finalize step uploads the reports that `persistInRepo` does **not**
keep, so large/media artifacts stay out of git history while still being
archived.

### modules

| Field | Default | Meaning |
| --- | --- | --- |
| `modules` | `[]` | Array of folder-pattern strings partitioning the repo into modules. Empty `[]` ⇒ no module dimension; the feature is inert and callers treat it as absent. |

A pattern is either a literal folder name (`core`) or a one-level glob
(`modules/*`). `scripts/modules.py` is the single source of the resolution
rule; the orchestrator and report producers call it rather than reimplementing
matching.

**Path → module id.** Given the patterns and a repo-relative forward-slash
path:

- Literal pattern `X` (no `*`): if the path's first segment is `X`, the module
  id is `X`.
- Glob pattern `P/*`: any path whose leading segments are `P/<sub>` — the
  subfolder itself or anything beneath it — has module id `P/<sub>`. Examples
  (pattern `modules/*`): `modules/payments` → `modules/payments`,
  `modules/payments/api/x.ts` → `modules/payments`.
- The longest / most-specific matching pattern wins. Patterns are evaluated by
  descending matched-prefix length for determinism.
- No pattern matches — any root-level file, or any folder not covered by a
  pattern — → module id `root`.
- The bare glob parent itself (`modules` with no subsegment) resolves to
  `root`. A file placed directly under `P/` with no subfolder cannot be
  told apart from a subfolder by path alone, so it takes id `P/<name>`; in
  practice `P/*` parents hold subfolders, and the repo→set list below only
  includes real subdirectories, so the report's module selector reflects the
  actual modules.

**Repo → module set.** The resolved set for a repo is `{ "root" }` ∪ each
literal pattern that exists as a top-level folder ∪ `P/<sub>` for each direct
subfolder of each `P/*` pattern's `P`. `root` is always present. Empty patterns
⇒ the set is exactly `{ "root" }` and the dimension is treated as absent.

`scripts/modules.py` exposes this rule directly:

- `python3 scripts/modules.py id <path> --patterns "core,foundation,modules/*"`
  — prints the single module id for `<path>`. Exit `0`; `1` on bad args. No
  git or repo access needed.
- `python3 scripts/modules.py list --patterns "core,foundation,modules/*" --repo <dir>`
  — prints the resolved module set, one id per line, `root` first then the
  rest lexically. Exit `0`; `1` bad args; `5` if `--repo` is not a directory.
- `--config <dev-process.json>` is an alternative to `--patterns`: the
  `modules` array is read from the config. With neither flag the pattern list
  is empty and only `root` is yielded.

## Blob storage credentials

Bucket/container and credentials come from the environment, never the config:

- **aws** — `DEV_RELEASE_S3_BUCKET` (required); standard AWS auth env
  (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`/`AWS_PROFILE`)
  used by the `aws` CLI. Uploads to `s3://$DEV_RELEASE_S3_BUCKET/<prefix>/`.
- **azure** — `DEV_RELEASE_AZURE_CONTAINER` (required) and either
  `AZURE_STORAGE_CONNECTION_STRING`, or `AZURE_STORAGE_ACCOUNT` +
  `AZURE_STORAGE_KEY`, used by the `az` CLI. Uploads to that container under
  `<prefix>/`.

Missing required env for the selected provider → exit 2 (precondition). An
upload failure → exit 4.

## gitignore the report dir

Add `reports.outputDir` (default `.agents/release-reports`) to the consuming
repo's `.gitignore` so report artifacts never get swept into an incidental
`git add -A`. `release_candidate_commit.sh` stages only the configured release
notes / changelog; the publish finalize step decides per `persistInRepo` what
(if anything) from `outputDir` is added to the amended commit versus uploaded.
