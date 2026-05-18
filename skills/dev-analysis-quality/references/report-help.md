# Reading the code-quality fragment

This part answers one question: is the code sound, sized, and within policy?
It rolls Semgrep (SAST), scc (size/complexity), OPA/Conftest (policy-as-code),
and an optional structural diff summary into one fragment.

## Findings — Semgrep

The Semgrep cards count findings by severity (error / warning / info); the
Findings table lists each check, file, line, severity, and message.

What to look for: any `Error`-severity finding. Errors are blocking — the
fragment goes `status: error`. Warnings are review-worthy; info is advisory.

What it means: `semgrep_error` above zero is a release blocker. Read the top
finding by severity, not the whole table, to find the priority fix.

## Metrics — scc

The size cards report lines of code, cyclomatic complexity, and file count;
the By-language table breaks those down per language.

What to look for: complexity that is out of proportion to code size, or a
single dominant language carrying most of it. These cards do not gate a
release — they are scale context, not a finding.

## Policy — OPA / Conftest

The Policy results table lists each policy-as-code denial or violation over
manifests / IaC, with the file and the rule that failed.

What to look for: any row. A policy failure is blocking — the fragment goes
`status: error` and `policy_failures` is above zero. An empty table is clean.

## Diff summary (role-written)

When a ref-range was supplied, the `code-diff-summary` role adds a structural
change narrative from the difftastic diff: what changed by area, the highest
blast-radius change, and refactor-vs-behavior-change.

What to look for: a changed public signature or a deleted module — the
"highest blast radius" line names what most likely breaks callers.
