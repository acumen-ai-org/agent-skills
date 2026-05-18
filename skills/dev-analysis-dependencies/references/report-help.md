# Reading the dependency supply-chain report

This fragment scans declared and resolved dependencies for known
vulnerabilities, inventories the package surface, and (for Rust) measures the
unsafe surface. Findings from Dependency-Check, Trivy, and Grype are
deduplicated by `(package, CVE)` so an overlapping CVE counts once.

## What to look for

- **Vulnerability severity cards.** Critical and high are the release-blocking
  band; medium and low are backlog. `Packages` is the distinct count of
  vulnerable libraries plus any SBOM / cargo-geiger components scanned — it
  frames the other counts (10 highs across 200 packages reads differently from
  10 across 12).
- **Vulnerable libraries table.** Level-1 rows are libraries: installed
  version(s), highest severity across that library's CVEs, the count of CVEs,
  and the ecosystem. Expand a row to see each CVE as a child — fixed version,
  that CVE's severity, and the scanners that flagged it.
- **Rust unsafe surface table** (only when cargo-geiger ran). Crates with a
  non-zero count of used `unsafe` functions plus expressions, highest first.
  This is surface, not a vulnerability — read it alongside, not instead of, the
  CVE table.

## What it means

- **A critical finding** sets the fragment status to `error`. Treat it as a
  release blocker until the library is upgraded to a fixed version or the CVE
  is documented as not applicable.
- **Highest severity is per library, not per CVE.** A library showing `high`
  may still hide a `medium` and a `low` child — expand before triaging.
- **One CVE, several scanners.** A CVE listing more than one scanner was
  confirmed independently; higher confidence, not a duplicate.
- **An empty findings table with a non-zero `Packages`** means the surface was
  scanned and nothing known is vulnerable — a clean result, not a skipped scan.
- **Fixed version blank** means no upstream fix is published yet; mitigation is
  removal, pinning away from the vulnerable range, or accepting the risk with a
  written rationale.

## Status

- `error` — at least one critical finding. Release blocker.
- `warn` — highs, mediums, or lows present, no critical. Triage before ship.
- `ok` — no known vulnerable dependency in the scanned surface.
