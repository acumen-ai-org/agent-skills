# dev-analysis-dependencies

> **Invocation.** This is an internal producer of `dev-report-framework`, not a standalone skill. The report pipeline `cd`s into this directory before running these steps, so every `scripts/…` self-call resolves here; all inputs are absolute paths. See the invocation contract in [`../../SKILL.md`](../../SKILL.md).

Producer Skill for the `dependencies` fragment. Each `scripts/run-*.sh`
scanner writes a raw file; `scripts/to-fragment.py` normalizes one or more raw
files into a single contract-valid fragment, deduplicating CVEs across
scanners. The [`references/supply-chain-synthesis.md`](references/supply-chain-synthesis.md)
role then enriches `summary` and adds the triage narrative. Scripts are run,
not read.

The fragment contract is owned by `dev-report-framework`; this Skill only
emits conformant JSON and validates it before handoff.

## Contents

- [Inputs](#inputs)
- [Engines and runtimes](#engines-and-runtimes)
- [Procedure](#procedure)
- [The two-stage contract](#the-two-stage-contract)
- [Synthesis](#synthesis)
- [Outputs](#outputs)
- [Failure modes](#failure-modes)
- [Exit codes](#exit-codes)

## Inputs

Every runner is positional: `run-<tool>.sh <target> <out_dir> [id]`.

| Input        | Required | Notes |
| ------------ | -------- | ----- |
| `<target>`   | yes      | Directory (or, for `run-grype.sh`, a Syft SBOM file) to scan. |
| `<out_dir>`  | yes      | Where the raw file and the fragment are written. |
| `[id]`       | no       | Fragment id stem; default `dependency-supply-chain`. Keep it stable across releases — it is the cross-release diff key. |

`id` must match `[a-z0-9-]+` (the contract). No env vars; the scanners need no
credentials.

## Engines and runtimes

| Runner | Engine | Runtime | Pinned image / install |
| ------ | ------ | ------- | ---------------------- |
| `run-depcheck.sh`     | OWASP Dependency-Check | Docker | `owasp/dependency-check:11.1.0` |
| `run-trivy.sh`        | Trivy | Docker | `aquasec/trivy:0.58.0` |
| `run-syft.sh`         | Syft (SBOM) | Docker | `anchore/syft:v1.18.1` |
| `run-grype.sh`        | Grype (vuln match) | Docker | `anchore/grype:v0.87.0` |
| `run-cargo-audit.sh`  | cargo-audit | cargo | `cargo install cargo-audit --locked` |
| `run-cargo-geiger.sh` | cargo-geiger (unsafe surface) | cargo | `cargo install cargo-geiger --locked` |

A runner never installs anything. If Docker or cargo is missing it prints the
exact install command and the pinned `docker run` line, then exits `3`. Pick
the runners that match the project's stacks: Dependency-Check / Trivy / Syft+
Grype for .NET/F#/TS-JS/Py and general filesystems; cargo-audit /
cargo-geiger for Rust. Running several and feeding all raw files to one
`to-fragment.py` call is the normal path — that is what the dedupe is for.

## Procedure

Copy this checklist into your response and tick as you go:

```
- [ ] 1. Scan      — run each applicable run-<tool>.sh <target> <out_dir>
- [ ] 2. Normalize — to-fragment.py <id> <raw...> <out_dir>/<id>.fragment.json
- [ ] 3. Synthesize — apply references/supply-chain-synthesis.md to the fragment
- [ ] 4. Validate  — validate_fragments.py <dir>  → must exit 0
```

### 1. Scan

Run every runner that matches a stack in the project. Example (Trivy +
Syft → Grype on the SBOM):

```bash
bash "scripts/run-trivy.sh" <target> <out_dir> <id>
bash "scripts/run-syft.sh"  <target> <out_dir> <id>
bash "scripts/run-grype.sh" <out_dir>/<id>.sbom.raw.json <out_dir> <id>
```

Each prints a trailing `TOOL <name> exit=<n>` line. Exit `3` → install the
tool as instructed and re-run. Exit `5` → the target/ref is invalid. Exit `2`
→ the tool ran but output is unparseable; the raw file is kept for diagnosis.

### 2. Normalize

```bash
python3 "scripts/to-fragment.py" \
  <id> <out_dir>/*.raw.json <out_dir>/<id>.fragment.json
```

Pass every raw file from step 1 as positional args before the output path.
`to-fragment.py` auto-detects each raw format (Dependency-Check, Trivy, Grype,
cargo-audit, cargo-geiger, Syft SBOM), deduplicates findings across
Dependency-Check / Trivy / Grype by `(package, CVE)`, groups the deduplicated
findings into one per-library `table` (level-1 rows are libraries — library,
installed version(s), highest severity, vuln count, ecosystem — with each
library's individual CVEs as expandable `children`), writes
`metrics{critical, high, medium, low, packages}` (`packages` counts distinct
libraries plus any SBOM/geiger components), and returns exit `4` when any
critical finding exists (fragment still written, `status: error`).

### 3. Synthesize

Apply [`references/supply-chain-synthesis.md`](references/supply-chain-synthesis.md)
to the fragment from step 2: it rewrites `summary` and appends the triage,
license-risk, and deduplication narrative sections, walking the per-library
table most-severe library first. Run it inline, or delegate it to an isolated
agent passing the role file as instructions and the fragment as input; merge
the result back into the fragment JSON.

### 4. Validate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dev-report-framework/scripts/validate_fragments.py" <out_dir>
```

Exit `0` → the fragment conforms; hand it to `dev-report-build`. Exit `3` →
fix and re-run. This is the feedback loop: validate → fix → repeat before any
build.

## The two-stage contract

Mirrors render→decode. Stage one (`run-<tool>.sh`) runs the tool and writes
`<out_dir>/<id>.raw.<ext>` (or `<id>.sbom.raw.json` / `<id>.<tool>.raw.json`
when a runner has a tool-specific name), printing `TOOL <name> exit=<n>`.
Stage two (`to-fragment.py`) reads any number of raw files and emits exactly
one fragment, `category: dependencies`, with the deduplicated findings grouped
per library (library rows, CVE children). The script writes only factual
`metrics{}` and `body[]`; the synthesis role adds `summary` + narrative.
Scripts never call an LLM.

## Synthesis

`references/supply-chain-synthesis.md` is the only role: per-library severity
triage (most-severe library first), license-risk narrative, and an explicit
note that findings were deduplicated across Dependency-Check / Trivy / Grype by
`(package, CVE)`. It never recomputes `metrics{}` — those are the script's
ground truth.

## Outputs

```
<out_dir>/
├── <id>.raw.json              # Trivy / Dependency-Check raw
├── <id>.grype.raw.json        # Grype raw (if run)
├── <id>.sbom.raw.json         # Syft CycloneDX SBOM (if run)
├── <id>.cargo-audit.raw.json  # cargo-audit raw (if run)
├── <id>.cargo-geiger.raw.json # cargo-geiger raw (if run)
└── <id>.fragment.json         # the dependencies fragment (validated)
```

`metrics{}`: `critical`, `high`, `medium`, `low`, `packages` (distinct
vulnerable libraries plus any SBOM/geiger components), plus
`unsafe_expressions` when Rust was scanned. `body[]`: a `metric-cards` severity
panel, the per-library findings `table` (level-1 rows = libraries, `children` =
their CVEs), an optional cargo-geiger unsafe `table`, then the synthesis role's
narrative.

## Failure modes

- **Docker / cargo missing** → runner prints the exact install line and the
  pinned `docker run` line, exits `3`. Never auto-installed.
- **Tool ran, output unparseable** → runner exits `2`, raw kept; `to-fragment.py`
  skips that file and uses the rest, or exits `2` if none parsed.
- **Same CVE from two scanners** → counted once; the CVE appears as a single
  child row under its library, listing every scanner that flagged it.
- **A critical finding exists** → fragment written, `status: error`,
  `to-fragment.py` exits `4`. This is a successful analysis of a failing
  project, not a runner error — distinct from exit `2`.
- **Target not a directory / SBOM not found** → runner exits `5`, nothing
  scanned.
- **Only an SBOM, no scan** → Syft alone yields a package inventory (the
  `packages` metric) with zero findings; pair it with Grype for vulnerabilities.

## Exit codes

`run-<tool>.sh` (mirrors the static-script contract):

| Code | Meaning |
| ---- | ------- |
| `0`  | Raw written; `TOOL <name> exit=0`. |
| `1`  | Bad arguments (missing positional). |
| `2`  | Tool ran but output unparseable; raw kept for diagnosis. |
| `3`  | Docker / cargo missing; install + run instructions printed. |
| `5`  | Target or SBOM path invalid. |

`to-fragment.py`:

| Code | Meaning |
| ---- | ------- |
| `0`  | Fragment written; `status` `ok`/`warn` (no critical). |
| `1`  | Bad arguments (missing positional). |
| `2`  | Every raw input unparseable; no fragment written. |
| `4`  | Fragment written with ≥ 1 critical finding; `status: error`. |
