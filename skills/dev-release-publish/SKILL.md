---
name: dev-release-publish
description: Finalizes a release candidate built by dev-release-candidate, driven by dev-process.json. Verifies the release candidate on origin, summarizes the release plan (informational, no approval gate), then rewrites the release-candidate commit so large report artifacts go to blob storage (AWS S3 or Azure Blob) instead of git history while the configured reports stay in the commit. It does not ask for approval, perform the production release, or notify — it can describe those steps when asked. Use to finalize an approved release candidate before the production release.
---

# dev-release-publish

A thin orchestrator. Runs after `dev-release-candidate` and re-reads
`dev-process.json` from the consuming repo.

**This Skill performs:** verify the release candidate (1), summarize the plan
(2, informational only), finalize the release-candidate commit (3) — upload the
reports that should not live in git history to blob storage and amend the
commit to keep only what `persistInRepo` says.

**This Skill does not perform** the approval decision, the production release
(tag + production branch), stakeholder notification, or the merge-back. Those
are real steps — when the user asks for the full process, describe them from
[Full process](#full-process-when-asked).

## Config

Contract:
[`../dev-release-candidate/references/dev-process-config.md`](../dev-release-candidate/references/dev-process-config.md)
(or `python3 "$S/dev_process.py" schema`).

## Inputs

| Env | Default | Notes |
| --- | --- | --- |
| `CLAUDE_PLUGIN_ROOT` | plugin root | locates `scripts/` |
| `DEV_RELEASE_REPO` | `.` | consuming repository |
| `DEV_RELEASE_CONFIG` | `$DEV_RELEASE_REPO/dev-process.json` | config path |
| `DEV_RELEASE_S3_BUCKET` | — | required when `blob.provider: aws` (with standard AWS auth env) |
| `DEV_RELEASE_AZURE_CONTAINER` | — | required when `blob.provider: azure` (with `AZURE_STORAGE_CONNECTION_STRING`, or `AZURE_STORAGE_ACCOUNT`+`AZURE_STORAGE_KEY`) |

`S="$CLAUDE_PLUGIN_ROOT/scripts"`. Finalize runs against the checked-out
release candidate branch, so check it out first.

## Procedure

```
- [ ] 0. Load config        → dev_process.py check
- [ ] 1. Verify candidate   → verify_release_candidate.sh
- [ ] 2. Plan (no approval) → summarize the release; do NOT gate
- [ ] 3. Finalize commit    → finalize_release_commit.sh
```

### 0. Load config

```bash
python3 "$S/dev_process.py" check
```

Exit 2 → invalid config; stop.

### 1. Verify the release candidate

```bash
bash "$S/verify_release_candidate.sh"
```

Checks `origin/<release-candidate>` exists and the analysis gate passed.
Exit 2 → candidate missing or gate marker absent (it must have been built and
pushed). Exit 3 → the analysis gate did not pass. Non-zero blocks finalize.

### 2. Plan (informational, no approval)

Summarize for the operator from `reports.outputDir/scope.json` and
`_summary.md`: the commit range, commit count, what will go to blob versus stay
in the commit. **Do not ask for approval and do not gate** — the go/no-go
decision is made outside this Skill.

### 3. Finalize the release-candidate commit

```bash
bash "$S/finalize_release_commit.sh"
```

There is already a release-candidate commit. This rewrites it so large
artifacts do not enter git history: it splits `reports.outputDir` by
`persistInRepo` (`all` keep all · `none` keep none · `except-media` keep
non-media), uploads the non-kept set to blob storage, amends the commit to add
only the kept set, then cleans the working report dir.

- `blob.provider: aws` → uploads to `s3://$DEV_RELEASE_S3_BUCKET/<prefix>/`
  (requires `DEV_RELEASE_S3_BUCKET` + AWS auth env).
- `blob.provider: azure` → uploads to `$DEV_RELEASE_AZURE_CONTAINER/<prefix>/`
  (requires `DEV_RELEASE_AZURE_CONTAINER` + Azure auth env).
- `blob.provider: none` → the non-kept reports are discarded (a warning is
  printed); only `persistInRepo` content stays.

Exit 2 → not on the release candidate branch, or required blob env missing.
Exit 4 → the upload failed. Amending rewrites the commit SHA; the old short
SHA is printed. The operator force-pushes the finalized candidate as part of
the (external) push/release step.

## Full process (when asked)

This Skill automates only verify + finalize. When the user asks for the whole
process, describe it; do **not** perform the external steps here.

| Step | Who |
| --- | --- |
| **A–B4** build the release candidate | `dev-release-candidate` |
| **B0/D/E** freeze, notify, push the candidate | external — see `dev-release-candidate` "Full process" |
| **1** verify the candidate on origin | this Skill |
| **2** approval / go decision | external — made by your team; this Skill only summarizes |
| **3** finalize the commit (reports → blob, amend) | this Skill |
| **F** production release: tag and update the production branch from the finalized candidate, then push | external/manual — e.g. `git push origin <rc-sha>:refs/heads/<production>` and an annotated tag, once approved |
| **D′** notify stakeholders the release shipped | external — your team's channel/comms tooling |
| **G** merge production back to `main`, lift the merge freeze, run any post-merge steps | external/manual |

## Outputs

- The release-candidate commit, amended to contain only `persistInRepo`
  content; the rest archived to blob storage (or discarded if `provider:none`).

## Failure modes

- **Candidate not verified** → step 1 exit 2/3; rebuild via
  `dev-release-candidate` and push it.
- **Missing blob env** → `finalize_release_commit.sh` exit 2; set
  `DEV_RELEASE_S3_BUCKET` / `DEV_RELEASE_AZURE_CONTAINER` and auth env.
- **Upload failed** → exit 4; retry after fixing credentials/connectivity (the
  commit is not amended until the upload succeeds).

## Exit codes

Shared across all `scripts/`: `0` ok · `1` usage · `2` precondition unmet
(wrong branch, missing env, candidate/gate absent) · `3` gate not passed ·
`4` remote/upload operation failed.
