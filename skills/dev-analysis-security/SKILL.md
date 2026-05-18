---
name: dev-analysis-security
description: Analyzes a repository's attack surface — static network egress/ingress inventory, Semgrep taint/security findings, and committed secrets — then emits one `security` report fragment. Runs a stdlib network extractor, gitleaks (Docker), an optional trufflehog verified-secret pass, and the shared repo-root run-semgrep.sh with a security ruleset. Data-flow is folded in here, not a separate Skill. Any verified secret blocks (status error). Use when assessing taint paths, network surface, leaked credentials, or attack surface between releases for a report.
---

# dev-analysis-security

Answers one question — *what is the attack surface: taint, network egress,
secrets?* — and emits exactly one report fragment, `category: security`.
Data-flow analysis is part of this Skill: the network egress/ingress
inventory, Semgrep taint paths, and secret findings fold into one
attack-surface fragment. Each runner is a two-stage `scripts/` step (run tool →
normalize); a `references/` role adds the narrative. Scripts never call an LLM.
The Skill is self-contained: the role lives in `references/`.

The Semgrep step calls the **repo-root shared runner**
(`scripts/run-semgrep.sh`), owned by `dev-analysis-quality`, with a security
ruleset. There is exactly one Semgrep runner in the repo — this Skill never
defines a second one
([shared-runner rule](../../docs/dev-skill-taxonomy.md#the-shared-runner-rule)).

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [Step detail](#step-detail)
- [The shared Semgrep runner](#the-shared-semgrep-runner)
- [Optional trufflehog](#optional-trufflehog)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input        | Default                       | Notes |
| ------------ | ----------------------------- | ----- |
| `$TARGET`    | —                             | Path to the source tree / repo to analyze. |
| `$OUT_DIR`   | —                             | Where raw tool output and the fragment land. |
| `$ID`        | `security`                    | Fragment id; `[a-z0-9-]+`, unique within a release. |
| `$RULESET`   | `p/security-audit`            | Semgrep security ruleset (registry id or local path). |

Runtime: `bash`, `python3` (standard library only), `git`. The network
extractor is pure stdlib and always runs. gitleaks and trufflehog are
detected, never installed: a missing tool prints its exact install line
**and** the pinned `docker run` line, then exits `3`. Docker images are pinned
in each runner (`gitleaks_image`, `trufflehog_image`, `semgrep_image`).
trufflehog is AGPL-3.0 and off by default — see
[Optional trufflehog](#optional-trufflehog).

## Procedure

Copy this checklist into the response and tick as each completes:

```
- [ ] 1. Network extractor → <out>/network.raw.json
- [ ] 2. gitleaks          → <out>/gitleaks.raw.json
- [ ] 3. Semgrep (security) → <out>/semgrep.raw.json
- [ ] 4. trufflehog         (only if TRUFFLEHOG_AGPL_ACK=true) → <out>/trufflehog.raw.json
- [ ] 5. Normalize         → <out>/<id>.fragment.json
- [ ] 6. Synthesis         → enrich summary + narrative body[0..2]
- [ ] 7. Validate          → validate_fragments.py exits 0
```

Run steps 1–4 in parallel where the tools are independent (they are). Steps
5–7 are sequential: normalize depends on the raw files, synthesis on the
fragment, validation last. Keep raw `*.raw.*` files out of the directory
passed to `validate_fragments.py` — point it at a directory holding only
fragment JSON.

## Step detail

### 1. Network extractor

```bash
python3 "scripts/run-network-extractor.py" "$TARGET" "$OUT_DIR"
```

Static egress/ingress inventory by import/call signature across Python, JS/TS,
Go, Rust, Java/Kotlin, C#, Ruby, PHP, and shell → `network.raw.json`. Pure
stdlib; always runs.

### 2. gitleaks

```bash
bash "scripts/run-gitleaks.sh" "$TARGET" "$OUT_DIR"
```

Docker, pinned `gitleaks_image`. Scans git history when `$TARGET` is a git
repo, else `--no-git` over the tree → `gitleaks.raw.json`.

### 3. Semgrep (security ruleset) — shared runner

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/run-semgrep.sh" "$TARGET" "$OUT_DIR" "${RULESET:-p/security-audit}"
```

The trailing `TOOL run-semgrep exit=<n>` line reports status. See
[The shared Semgrep runner](#the-shared-semgrep-runner). Skip-and-continue if
the runner exits `3` (Semgrep + Docker both missing) — the fragment is still
produced from the other tools.

### 4. trufflehog (only if `TRUFFLEHOG_AGPL_ACK=true`)

```bash
bash "scripts/run-trufflehog.sh" "$TARGET" "$OUT_DIR"
```

Optional deeper verified-secret pass. Gated by AGPL acknowledgement; see
[Optional trufflehog](#optional-trufflehog).

### 5. Normalize

```bash
python3 "scripts/to-fragment.py" "${ID:-security}" \
  "$OUT_DIR/${ID:-security}.fragment.json" \
  --network "$OUT_DIR/network.raw.json" \
  --gitleaks "$OUT_DIR/gitleaks.raw.json" \
  --semgrep "$OUT_DIR/semgrep.raw.json"
```

Add `--trufflehog "$OUT_DIR/trufflehog.raw.json"` when step 4 ran. Pass only
the raws that exist. The script writes factual `metrics{}` and factual
`body[]` and sets `status` from the evidence — any verified secret →
`status: error`, exit `4`.

### 6. Synthesis

Follow [`references/threat-synthesis.md`](references/threat-synthesis.md) with
the fragment from step 5 as input. It sets `summary` and inserts three
narrative `markdown` sections (attack surface, secrets, data-flow & taint),
each tagged `"menu": "Assessment"` so the narrative lands under its own
top-menu group. The script-emitted sections carry their own groups: the
network cards and egress/ingress tables under `Network`, the secret cards and
table under `Secrets`, the Semgrep cards and findings table under `Taint`.
Run inline, or delegate to an isolated agent passing the role file as
instructions for fresh context. Write the enriched fragment back to the same
path.

### 7. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" "$FRAGMENT_DIR"
```

`$FRAGMENT_DIR` holds the fragment JSON only (not the raws). Only proceed when
this exits `0`. Exit `3` lists per-file errors on stderr — fix the fragment
and re-run.

## The shared Semgrep runner

`scripts/run-semgrep.sh` (repo root, owned by `dev-analysis-quality`)
signature:

```
run-semgrep.sh <target> <out_dir> <ruleset>
```

The third positional is the ruleset by design: `dev-analysis-quality` passes a
quality/SAST ruleset; this Skill calls the **same file** with a
taint/network/security ruleset (`p/security-audit`, `p/owasp-top-ten`). Adding
a second Semgrep runner is forbidden by the
[shared-runner rule](../../docs/dev-skill-taxonomy.md#the-shared-runner-rule).
It writes `semgrep.raw.json`; `to-fragment.py` normalizes it into the security
fragment.

## Optional trufflehog

`scripts/run-trufflehog.sh` is a deeper verified-secret pass and is **never on
the default path**. trufflehog is AGPL-3.0; the script refuses to run without
`TRUFFLEHOG_AGPL_ACK=true` (exits `3`, treated like an absent optional tool).
gitleaks is the portable default; no pipeline depends on trufflehog. When both
run, `to-fragment.py` lists each finding with its scanner in the secrets
table; either scanner's verified finding blocks.

## Outputs

`$OUT_DIR/<id>.fragment.json` — one `category: security` fragment that passes
`validate_fragments.py`. Raw tool outputs (`network.raw.json`,
`gitleaks.raw.json`, `semgrep.raw.json`, optional `trufflehog.raw.json`) are
kept alongside for diagnosis and re-runs.

## Failure modes

- **gitleaks/trufflehog + Docker both missing** → runner prints the install
  line and the pinned `docker run` line, exits `3`. Never auto-installs.
  Install or enable Docker and re-run; the network extractor still produces a
  fragment without them.
- **Semgrep + Docker both missing** → shared runner exits `3`; skip the
  Semgrep input and normalize from the other tools.
- **Tool ran but output unparseable** → runner exits `2`, keeps the raw file.
  Re-run that step; pass only parseable raws to `to-fragment.py`.
- **Verified secret present** → a successful analysis: `to-fragment.py` writes
  the fragment with `status: error` and exits `4`. Distinct from a runner
  breaking (exit `2`).
- **trufflehog invoked without acknowledgement** → exits `3` by design; not a
  failure of the default pipeline.

## Exit codes

Every runner and `to-fragment.py` follow the standard table:

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment / raw written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Tool ran but output unparseable; raw kept for diagnosis. |
| `3`  | Required tool/Docker missing (or trufflehog not acknowledged); install + docker instructions printed. |
| `4`  | Tool ran and reported a verified secret; fragment written, `status: error`. |
| `5`  | Target or ref invalid (path absent, not a git repo). |
