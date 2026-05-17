# Dev-tooling Skill Taxonomy

The naming and ownership rules for the development-analysis and reporting
Skills. A new tool gets placed by applying the assignment rule below — there is
one right answer, not a judgement call.

## Contents

- [Prefixes](#prefixes)
- [Categories](#categories)
- [The assignment rule](#the-assignment-rule)
- [The shared-runner rule](#the-shared-runner-rule)
- [Naming](#naming)
- [Why category Skills, not one per tool](#why-category-skills-not-one-per-tool)

## Prefixes

Every Skill in this family carries one of three prefixes. The prefix is a
contract about what the Skill is allowed to do.

| Prefix          | Does                                                                 | Never does                                       | Output |
| --------------- | -------------------------------------------------------------------- | ------------------------------------------------ | ------ |
| `dev-analysis-` | Reads code, git history, manifests, or docs and reports findings.    | Mutates the target. Gates a pipeline (it reports `status`; the consumer decides). | One or more report fragments. |
| `dev-test-`     | Executes the system under test and verifies behavior.                | Reports without running the system.              | A report fragment whose `status` is the pass/fail verdict. |
| `dev-report-`   | Consumes fragments and/or orchestrates the above into a deliverable. | Owns an analyzer or runs a tool itself.          | A human deliverable (a report folder, a Slidev deck). |

The static/LLM split is physical inside every `dev-analysis-`/`dev-test-`
Skill: a script in `scripts/` produces the factual `metrics{}` and factual
`body[]`; a role in `references/*-synthesis.md` produces the narrative. Scripts
never call an LLM.

## Categories

A `dev-analysis-`/`dev-test-` Skill owns exactly one **question**. The category
is that question, and it is the fragment's `category` field. The set is fixed
(closed enum — the report framework's left-nav depends on it):

| Category       | Question it answers                                                  | Owning Skill |
| -------------- | -------------------------------------------------------------------- | ------------ |
| `architecture` | Does the code's structure match the intended structure?              | `dev-analysis-architecture` |
| `evolution`    | How has the codebase changed over releases, and where is the churn?  | `dev-analysis-evolution` |
| `dependencies` | What do we depend on, and is any of it vulnerable or stale?          | `dev-analysis-dependencies` |
| `quality`      | Is the code sound, sized, and within policy?                         | `dev-analysis-quality` |
| `security`     | What is the attack surface — taint, network egress, secrets?         | `dev-analysis-security` |
| `schema`       | Did the API/data contracts change, and are the changes breaking?     | `dev-analysis-schema` |
| `contracts`    | Do providers still honor the contracts their consumers depend on?    | `dev-test-contracts` |
| `mission`      | Does this change serve the product's stated mission?                 | `dev-analysis-mission` |
| `test-coverage`| What is unit-test coverage?                                          | none — empty slot, see below |
| `test-reports` | What do the end-to-end test runs say?                                | none — empty slot, see below |
| `overview`     | What is the release at a glance?                                     | `dev-report-overview` |

`test-coverage` and `test-reports` are **empty slots**: no Skill ships a
producer. The consuming repo wires its own coverage/e2e tool to these
categories via a `dev-process.json` `analysis`/`review` entry. The framework's
left-nav shows them so the structure is present even before the repo fills
them; no placeholder Skill exists (the repo's no-scaffolding rule).

Three `dev-report-` Skills sit above the categories: `dev-report-framework`
(assembles fragments into a standalone HTML report folder),
`dev-report-release-diff` (a multi-perspective `git diff` → Slidev deck), and
`dev-report-overview` (runs last; emits the pinned `overview` fragment — a
content-to-image infographic + scope bullets — that the framework shows as the
default landing page).

Adding a category is a deliberate change: it touches the fragment-schema enum
and the report framework's navigation. Do not let a `dev-analysis-` Skill
invent a category to avoid the assignment rule.

## The assignment rule

Apply this to every new tool. The category is the **question the tool helps
answer**, never the tool's name.

```
Does the tool execute the system under test (run it, call it, verify behavior)?
  └─ yes → dev-test-<question>
Does it only read code / history / config / docs and produce findings?
  └─ yes → dev-analysis-<question>, where <question> is one of the fixed
            categories above — NOT the tool name.
Does it only consume fragments or present results?
  └─ yes → dev-report-<deliverable>
A tool that plausibly fits two questions → assign it to the question its
  PRIMARY output answers; expose the secondary use as a ruleset/flag on the
  existing runner, never as a second Skill or a second runner.
```

Worked examples:

- `dependency-cruiser` produces a module graph and boundary violations → the
  question is "does structure match intent" → `dev-analysis-architecture`. Not
  a `dev-analysis-dependency-cruiser` Skill.
- `Trivy` reports vulnerable packages → "what do we depend on and is it
  vulnerable" → `dev-analysis-dependencies`.
- `pact` runs provider verification against real consumer contracts → it
  executes the system → `dev-test-contracts`.
- `git-of-theseus` reports code survival across history → "how has the
  codebase changed" → `dev-analysis-evolution`.

## The shared-runner rule

When one tool serves two questions, the runner script has exactly one owner;
the second Skill calls it with a different ruleset.

Semgrep is the precedent. `dev-analysis-quality` owns `run-semgrep.sh` and
invokes it with quality/SAST rulesets. `dev-analysis-security` calls the **same
runner** with taint/network rulesets. There is never a second Semgrep runner.
If a third Skill needs the runner, the runner is promoted to a repo-level
`scripts/` per the promote-on-second-consumer rule in
[repository-structure.md](repository-structure.md#repo-level-references-hooks-scripts).

The same applies to data collectors: `dev-analysis-evolution` owns the git
diff/stat collectors; `dev-report-release-diff` reuses them rather than
duplicating `git diff` parsing.

## Naming

Extends the repo [naming conventions](repository-structure.md#naming-conventions):

| Thing            | Rule |
| ---------------- | ---- |
| Skill directory  | `<prefix><question-or-deliverable>`, lowercase + hyphens, matches `name:` in its `SKILL.md`. E.g. `dev-analysis-architecture`. |
| Tool runner      | `run-<tool>.sh` (or `.py`), verb-first, one tool per runner. |
| Normalizer       | `to-fragment.py` — the per-Skill stdlib step that turns raw tool output into a contract fragment. |
| Synthesis role   | `references/<question>-synthesis.md` (or `<purpose>-narrative.md`). Plain markdown, no frontmatter, strict output template. |

## Why category Skills, not one per tool

One Skill per question keeps the surface small and the report navigation
stable. A new tool that answers an existing question is a new `scripts/` runner
inside the existing Skill — zero new Skills, zero framework changes, zero
new nav entries. One Skill per tool would fragment the `skills/` index, split a
single question's findings across several fragments, and make "what changed in
dependencies this release" un-navigable. The seam that makes this work is the
report-fragment contract in
[dev-report-framework.md](dev-report-framework.md): every runner, regardless of
tool, emits the same shape.
