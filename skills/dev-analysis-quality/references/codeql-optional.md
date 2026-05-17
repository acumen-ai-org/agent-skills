# CodeQL — optional, licensing-gated

CodeQL is **never on the default path** of `dev-analysis-quality`. Semgrep
CE (the shared `run-semgrep.sh`) is the portable default and the only SAST
engine any pipeline depends on. CodeQL is an opt-in deeper pass, enabled
only where its license permits, and no fragment, build, or release ever
requires it.

## The licensing gate

The CodeQL CLI is free to run on **public / open-source** repositories and
for academic research. On **private or proprietary** code, automated
CodeQL analysis requires GitHub Advanced Security (a paid product). Running
CodeQL on private code without that entitlement violates the CodeQL terms.

Because of this split, `run-codeql.sh` refuses to run unless the caller
explicitly acknowledges the license applies to the target:

```
CODEQL_LICENSE_ACK=true bash scripts/run-codeql.sh <target> <out_dir> <language>
```

Without `CODEQL_LICENSE_ACK=true` the runner prints this gate and exits
`3` — the same exit a missing tool uses, so the default pipeline treats an
un-acknowledged CodeQL exactly like an absent optional tool: it is skipped,
not failed.

## When it is permitted to enable it

Set `CODEQL_LICENSE_ACK=true` only when **one** of these holds and you have
confirmed it for the specific target:

- The repository is public / open-source.
- The analysis is academic research as defined by the CodeQL terms.
- The organization holds a GitHub Advanced Security entitlement covering
  this repository.

If none holds, do not set the variable. There is no fallback that runs
CodeQL anyway — Semgrep already covered the default SAST need.

## What it adds when enabled

`run-codeql.sh` builds a CodeQL database for `<language>` (one of
`csharp`, `javascript`, `python`) and runs the standard query suite,
emitting SARIF at `<out_dir>/codeql.raw.sarif`. CodeQL's interprocedural
data-flow finds taint paths Semgrep's pattern rules miss; treat it as a
supplementary signal layered onto the Semgrep-based `quality` fragment, not
a replacement for it. Normalizing SARIF into the fragment is out of scope
for v1 — the raw SARIF is kept for manual review.

## Out of scope

Making any pipeline depend on CodeQL. Auto-enabling it. Bypassing the
license acknowledgement. Replacing Semgrep with CodeQL on the default path.
SARIF-to-fragment normalization (raw SARIF only in v1).
