# dev-analysis-quality

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

Answers one question — *is the code sound, sized, and within policy?* — and
emits exactly one report fragment, `category: quality`. Each runner is a
two-stage `scripts/` step (run tool → normalize); a `references/` role adds
the narrative. Scripts never call an LLM. The Skill is self-contained: roles
live in `references/`.

This Skill **owns the shared Semgrep runner**. It lives at the repo root
(`scripts/run-semgrep.sh`), not in this Skill, because
`dev-analysis-security` calls the same file with a security ruleset. There
is exactly one Semgrep runner in the repo.

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [Step detail](#step-detail)
- [The shared Semgrep runner](#the-shared-semgrep-runner)
- [Optional CodeQL](#optional-codeql)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input         | Default                | Notes |
| ------------- | ---------------------- | ----- |
| `$TARGET`     | —                      | Path to the source tree to analyze. |
| `$OUT_DIR`    | —                      | Where raw tool output and the fragment land. |
| `$ID`         | `quality`              | Fragment id; `[a-z0-9-]+`, unique within a release. |
| `$RULESET`    | `p/ci`                 | Semgrep ruleset for the quality pass (registry id or local path). |
| `$POLICY_DIR` | unset → policy skipped | Rego policy dir for OPA/Conftest. |
| `$REF_RANGE`  | unset → diff skipped   | `<ref>..<ref>` for the difftastic structural diff. |

Runtime: `bash`, `python3` (standard library only), `git`. Tools are
detected, never installed: a missing tool prints its exact install line
**and** the pinned `docker run` line, then exits `3`. Docker images are
pinned in each runner (`semgrep_image`, `opa_image`, `conftest_image`,
`scc_image`, `difftastic_image`).

## Procedure

Copy this checklist into the response and tick as each completes:

```
- [ ] 1. Semgrep      → <out>/semgrep.raw.json
- [ ] 2. scc          → <out>/scc.raw.json
- [ ] 3. Policy        (only if $POLICY_DIR set) → <out>/opa.raw.json | conftest.raw.json
- [ ] 4. Difftastic    (only if $REF_RANGE set)  → <out>/difftastic.raw.txt
- [ ] 5. Normalize    → <out>/<id>.fragment.json
- [ ] 6. Synthesis    → enrich summary + narrative body[0]
- [ ] 7. Diff prose    (only if step 4 ran)
- [ ] 8. Validate     → validate_fragments.py exits 0
```

Run steps 1–4 in parallel where the tools are independent (they are). Steps
5–8 are sequential: normalize depends on the raw files, synthesis on the
fragment, validation last.

## Step detail

### 1. Semgrep (quality ruleset)

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/run-semgrep.sh" "$TARGET" "$OUT_DIR" "${RULESET:-p/ci}"
```

The trailing `TOOL run-semgrep exit=<n>` line reports status. See
[The shared Semgrep runner](#the-shared-semgrep-runner).

### 2. scc

```bash
bash "scripts/run-scc.sh" "$TARGET" "$OUT_DIR"
```

LOC, file count, and cyclomatic complexity per language → `scc.raw.json`.

### 3. Policy (only if `$POLICY_DIR` set)

Choose by what the target is: structured config / IaC / manifests →
Conftest; an explicit Rego query over a single input document → OPA.

```bash
bash "scripts/run-conftest.sh" "$TARGET" "$OUT_DIR" "$POLICY_DIR"
bash "scripts/run-opa.sh"      "$TARGET" "$OUT_DIR" "$POLICY_DIR"
```

### 4. Difftastic (only if `$REF_RANGE` set)

```bash
bash "scripts/run-difftastic.sh" "$TARGET" "$OUT_DIR" "$REF_RANGE"
```

`$TARGET` here is the repo root. Writes `difftastic.raw.txt` for step 7.

### 5. Normalize

```bash
python3 "scripts/to-fragment.py" "${ID:-quality}" \
  "$OUT_DIR/${ID:-quality}.fragment.json" \
  --semgrep "$OUT_DIR/semgrep.raw.json" \
  --scc "$OUT_DIR/scc.raw.json"
```

Add `--opa <file>` / `--conftest <file>` when step 3 ran. The script writes
factual `metrics{}` and factual `body[]` and sets `status` from the
evidence (`error` + exit `4` on any Semgrep error or policy failure).

### 6. Synthesis

Follow [`references/quality-synthesis.md`](references/quality-synthesis.md)
with the fragment from step 5 as input. It sets `summary` and prepends one
`markdown` body section. Run inline, or delegate to an isolated agent
passing the role file as instructions for fresh context. Write the enriched
fragment back to the same path.

### 7. Diff prose (only if step 4 ran)

Follow [`references/code-diff-summary.md`](references/code-diff-summary.md)
with `difftastic.raw.txt` and `$REF_RANGE`. Its output is the structural
change narrative; append it as an additional `markdown` body section carrying
`"menu": "Diff summary"` so it lands under its own top-menu group. The
Semgrep cards/findings sit under `Findings`, the scc cards/by-language under
`Metrics`, the policy table under `Policy`; the leading untagged default item
(named after the fragment title) collects the `quality-synthesis` Assessment.
`dev-report-release-diff` reuses this same role.

### 8. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" "$OUT_DIR"
```

Only proceed when this exits `0`. Exit `3` lists per-file errors on stderr —
fix the fragment and re-run.

## The shared Semgrep runner

`scripts/run-semgrep.sh` (repo root) signature:

```
run-semgrep.sh <target> <out_dir> <ruleset>
```

The third positional is the ruleset by design: `dev-analysis-quality`
passes a quality/SAST ruleset (`p/ci`, `p/default`, or a local path);
`dev-analysis-security` calls the **same file** with a taint/network
ruleset (`p/security-audit`, `p/owasp-top-ten`). Adding a second Semgrep
runner is forbidden by the
[shared-runner rule](../../../../docs/dev-skill-taxonomy.md#the-shared-runner-rule).
It writes `semgrep.raw.json`; `to-fragment.py` normalizes it.

## Optional CodeQL

`scripts/run-codeql.sh` is gated by
[`references/codeql-optional.md`](references/codeql-optional.md) and is
**never on the default path**. It refuses to run without
`CODEQL_LICENSE_ACK=true` (exits `3`, treated like an absent optional
tool). Semgrep is the portable default; no pipeline depends on CodeQL.

## Outputs

`$OUT_DIR/<id>.fragment.json` — one `category: quality` fragment that
passes `validate_fragments.py`. Raw tool outputs (`semgrep.raw.json`,
`scc.raw.json`, optional `opa.raw.json`/`conftest.raw.json`,
`difftastic.raw.txt`) are kept alongside for diagnosis and re-runs.

## Failure modes

- **Tool + Docker both missing** → runner prints the install line and the
  pinned `docker run` line, exits `3`. Never auto-installs. Install or
  enable Docker and re-run that step.
- **Tool ran but output unparseable** → runner exits `2`, keeps the raw
  file for diagnosis. The fragment is not written.
- **Semgrep errors or policy failures present** → a successful analysis:
  `to-fragment.py` writes the fragment with `status: error` and exits `4`.
  Distinct from a runner breaking (exit `2`).
- **Bad / missing ref for difftastic** → runner exits `5`; the diff prose
  step is skipped, the rest of the fragment is still produced.
- **CodeQL invoked without acknowledgement** → exits `3` by design; not a
  failure of the default pipeline.

## Exit codes

Every runner and `to-fragment.py` follow the standard table:

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment / raw written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Tool ran but output unparseable; raw kept for diagnosis. |
| `3`  | Required tool/Docker missing (or CodeQL not acknowledged); install + docker instructions printed. |
| `4`  | Tool ran and reported blocking findings; fragment written, `status: error`. |
| `5`  | Target or ref invalid (not a git repo, ref not found, path absent). |
