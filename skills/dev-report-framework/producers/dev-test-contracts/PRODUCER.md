# dev-test-contracts

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

`dev-test-` Skill: it **executes** the provider against real consumer
contracts. It does not statically inspect the contract — it runs the system
and the fragment `status` is the verification verdict. The static/LLM split is
physical: `scripts/` produce the factual `metrics{}` + `body[]`;
[`references/contract-results-synthesis.md`](references/contract-results-synthesis.md)
adds the narrative. Scripts never call an LLM.

## Contents

- [Inputs](#inputs)
- [Procedure](#procedure)
- [1. Verify](#1-verify)
- [2. Normalize to a fragment](#2-normalize-to-a-fragment)
- [3. Validate the fragment](#3-validate-the-fragment)
- [4. Synthesize the narrative](#4-synthesize-the-narrative)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

| Input            | Default | Notes |
| ---------------- | ------- | ----- |
| `<provider-dir>` | —       | The provider project. Its manifest selects the verifier stack: `package.json` → pact-js, `*.csproj` → PactNet, `pyproject.toml`/`requirements*.txt` → pact-python, `Cargo.toml` → pact-rust. |
| `<out_dir>`      | —       | Where the raw result and the fragment land. |
| `<pacts-dir>`    | —       | Directory of consumer pact JSON files. Not required if `PACT_BROKER_BASE_URL` is set. |
| `PACT_BROKER_BASE_URL` | unset | Optional broker serving consumer pacts instead of `<pacts-dir>`. |
| `PACT_PROVIDER_BASE_URL` | `http://localhost:8080` | Where the running provider is reachable (pact-python path). |

The provider must be reachable when the verifier runs — this Skill verifies a
running system. The verifier is **detected, never installed**: if the stack's
runtime is absent the runner prints the exact install line plus the pinned
broker `docker run` line and exits `3`.

`S="scripts"` below.

## Procedure

Track progress:

```
- [ ] 1. Verify       → run-pact-verify.sh → <out_dir>/pact-verify.raw.json
- [ ] 2. Normalize    → to-fragment.py     → <out_dir>/fragments/contracts.fragment.json
- [ ] 3. Validate     → validate_fragments.py (exit 0 required)
- [ ] 4. Synthesize    → contract-results-synthesis.md (enrich summary + body[])
```

### 1. Verify

```bash
bash "$S/run-pact-verify.sh" <provider-dir> <out_dir> <pacts-dir>
```

It detects the provider stack, runs that stack's pact verifier against the
consumer pacts (or the broker), and writes `<out_dir>/pact-verify.raw.json`
plus `<out_dir>/pact-verify.log`. The raw JSON carries an additive
`detected_stack` string (`pact-js` | `pact-jvm` | `pact-python` | `pact-go` |
`""` when the stack is unknown) alongside the verifier's own fields; the
existing raw shape is unchanged. The trailing `TOOL run-pact-verify exit=<n>`
line reports the outcome. Exit `3` means the verifier runtime is missing —
follow the printed install instructions, do not auto-install. Exit `4` means
the verifier ran and reported failed interactions; **continue to step 2**, the
fragment must still be written.

### 2. Normalize to a fragment

```bash
python3 "$S/to-fragment.py" contracts "<out_dir>/pact-verify.raw.json" "<out_dir>/fragments/contracts.fragment.json"
```

Emits one `category: contracts` fragment into a `fragments/` subdirectory so
the validator (step 3) sees only fragments, never the raw result or log. Every
interaction is enumerated in the "Verified interactions" table; `metrics{}`
carries the counts. `status` is the verdict: `error` if any interaction failed
(the script exits `4`), `warn` if all passed but one or more had no provider
state (or nothing was verified), `ok` if all passed and all stated. The
interactions table carries a per-section `status` mirroring that verdict
(`error` if any failed, `warn` if stateless or nothing verified, else `ok`).
After the table the script always emits a "Suggested provider verification
stack" markdown section (`status: info`, `menu: Suggested stack`): it explains
the four parts of a verification stack and names a concrete verifier picked by
a static dict keyed on the raw `detected_stack`. It is advisory — nothing is
wired this run. The fragment also carries a `help` markdown string from
[`references/report-help.md`](references/report-help.md) (the `❓` header
link), absent only if that file cannot be read.

### 3. Validate the fragment

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" "<out_dir>/fragments"
```

Point it at `<out_dir>/fragments` — the validator scans every `*.json` in the
directory, so it must see only fragments, never `pact-verify.raw.json`. Exit
`0` is the gate: only proceed when it passes. Exit `3` lists per-file contract
errors — fix and re-run step 2.

### 4. Synthesize the narrative

Follow [`references/contract-results-synthesis.md`](references/contract-results-synthesis.md)
with the validated fragment as input. It produces a one-line plain-text
`summary` and one `markdown` section to prepend to `body[]`: the verdict, the
failed interactions verbatim, and every contract verified without a provider
state. Re-validate (step 3) after merging the narrative back in.

## Outputs

- `<out_dir>/pact-verify.raw.json` — raw verifier result.
- `<out_dir>/pact-verify.log` — verifier stdout/stderr (kept for diagnosis).
- `<out_dir>/fragments/contracts.fragment.json` — the contract fragment,
  validated, with the synthesized `summary` and narrative `body[]`.

## Failure modes

- **Verifier runtime missing** → exit `3`, install line + pinned broker
  `docker run` line printed; never auto-installed.
- **Provider not running / unreachable** → the verifier reports failed
  interactions; status `error`, exit `4`. This is a real verification failure,
  not a runner break.
- **Verifier produced no / invalid JSON** → exit `2`, raw log kept; the
  verifier integration needs fixing before a fragment can be written.
- **Pacts dir absent and no broker** → exit `5`; provide `<pacts-dir>` or
  `PACT_BROKER_BASE_URL`.
- **Interaction passed with no provider state** → status `warn`; the synthesis
  role surfaces each one as a weak pass.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment written; `status` `ok`/`warn`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Verifier ran but output unparseable; raw kept for diagnosis. |
| `3`  | Verifier runtime/Docker missing; install + docker instructions printed. |
| `4`  | Verifier ran and an interaction failed; fragment written, `status: error`. |
| `5`  | Provider dir or pacts source invalid. |

`0` vs `4`: a clean run that finds a broken contract is still a successful
verification (`status: error`, exit `4`) — distinct from the runner itself
breaking (exit `2`).
