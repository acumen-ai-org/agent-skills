# Authoring Skills

A working summary of Anthropic's *Skill authoring best practices*
(<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>).
Read the original for full detail and examples; this is the operational subset
this repo enforces.

## Contents

- [Core principles](#core-principles)
- [Frontmatter](#frontmatter)
- [The description field](#the-description-field)
- [Progressive disclosure](#progressive-disclosure)
- [Workflows and feedback loops](#workflows-and-feedback-loops)
- [Scripts](#scripts)
- [Content rules](#content-rules)
- [Anti-patterns](#anti-patterns)
- [Iteration](#iteration)
- [Checklist](#checklist)

## Core principles

1. **Concise is key.** The context window is a public good. Only the `name` +
   `description` are preloaded; `SKILL.md` is read when the Skill triggers, and
   then every token competes with everything else. Default assumption: the
   model is already smart. For each sentence ask "does the model already know
   this?" — if yes, cut it.
2. **Match degrees of freedom to fragility.** High freedom (prose steps) when
   many approaches work and context decides. Medium freedom (parameterized
   pseudocode/scripts) when a preferred pattern exists. Low freedom (one exact
   script, no options) when the operation is fragile and consistency is
   critical. Analogy: narrow bridge → exact guardrails; open field → general
   direction.
3. **Test with every model you'll run it on.** Haiku may need more guidance;
   Opus needs less hand-holding. Aim for instructions that work across all.

## Frontmatter

`SKILL.md` requires exactly two fields:

```yaml
---
name: content-to-image
description: <what it does AND when to use it — third person>
---
```

- `name`: ≤ 64 chars, lowercase letters/numbers/hyphens only, no XML tags, no
  reserved words (`anthropic`, `claude`). Prefer gerund form
  (`processing-pdfs`); noun phrases (`pdf-processing`) are acceptable.
- `description`: ≤ 1024 chars, non-empty, no XML tags.

## The description field

This is the single most important line — the model uses it to pick this Skill
out of potentially 100+. It must state **what the Skill does and when to use
it**, with concrete trigger terms.

- **Third person, always.** It is injected into the system prompt. ✅
  "Processes Excel files and generates reports." ❌ "I can help you…" / "You
  can use this to…".
- **Specific, with key terms.** ✅ "Extract text and tables from PDF files,
  fill forms, merge documents. Use when working with PDFs, forms, or document
  extraction." ❌ "Helps with documents."

## Progressive disclosure

`SKILL.md` is a table of contents, not the manual.

- Keep the `SKILL.md` body **under 500 lines**. Split before you hit it.
- Push detail into separate files loaded only when needed:
  - **Pattern 1 — guide + references:** quick start inline; "Advanced: see
    `FORMS.md`".
  - **Pattern 2 — domain split:** `reference/finance.md`,
    `reference/sales.md` — load only the relevant domain.
  - **Pattern 3 — conditional detail:** basic inline, link advanced.
- **Keep references one level deep.** Everything links directly from
  `SKILL.md`. The model may only `head` a file reached through a chain of
  links, so nested references → incomplete reads.
- **Reference files > 100 lines get a table of contents** at the top, so a
  partial read still reveals the full scope.
- Bundled files cost **zero context until read** — bundle comprehensive
  material freely; just keep `SKILL.md` itself lean.

## Workflows and feedback loops

- Break complex tasks into explicit numbered steps. For long ones, give a
  checklist the model copies into its response and ticks off — it prevents
  skipped validation steps.
- Build **feedback loops**: run validator → fix → repeat. The "validator" can
  be a script or a reference doc the model checks against. "Only proceed when
  validation passes."
- For high-stakes/batch/destructive work use **plan → validate → execute**:
  emit a structured plan file, validate it with a script, then act.

## Scripts

For Skills with executable steps:

- **Solve, don't punt.** Scripts handle their own error cases instead of
  failing and leaving the model to improvise.
- **No voodoo constants.** Every magic number is justified in a comment
  ("3 retries: most intermittent failures resolve by the second").
- **Prefer scripts for deterministic ops** — more reliable than regenerated
  code, saves tokens, consistent.
- **State execute-vs-read intent.** "Run `analyze_form.py`" (execute) vs "See
  `analyze_form.py` for the algorithm" (read). Execution is usually preferred.
- **Don't assume installs.** List required packages; note no network access on
  the API runtime.

## Content rules

- **No time-sensitive info.** Don't write "before August 2025, use the old
  API." Put superseded guidance in a collapsed "Old patterns" section instead.
- **One term, used consistently.** Pick "field" or "box", "extract" or
  "pull" — not a mix. Consistency aids comprehension.
- **Concrete examples beat descriptions.** Provide input/output pairs where
  output quality depends on style (e.g. commit messages).
- **Forward slashes only** in paths, even on Windows.

## Anti-patterns

- Verbose explanation of things the model already knows.
- Too many options ("use pypdf or pdfplumber or PyMuPDF or…"). Give one
  default with a single escape hatch.
- Windows-style backslash paths.
- Deeply nested references.
- Time-sensitive statements baked into the main body.

## Iteration

- **Build evaluations first.** Run the task *without* a Skill, document the
  failures, write ~3 scenarios that capture them, baseline, then write the
  minimum content to pass. Solve real gaps, not imagined ones.
- **Two-Claude loop.** "Claude A" helps you author; "Claude B" (fresh, Skill
  loaded) does real tasks; bring B's failures back to A. Iterate on observed
  behavior, not assumptions. Watch how the model navigates the Skill — ignored
  files are dead weight; repeatedly-read files maybe belong in `SKILL.md`.

## Checklist

Before merging a Skill:

**Core quality**
- [ ] `description` is third person, specific, says what *and* when.
- [ ] `SKILL.md` body < 500 lines.
- [ ] Detail in separate files; references one level deep.
- [ ] Reference files > 100 lines have a table of contents.
- [ ] No time-sensitive info (or in an "Old patterns" section).
- [ ] Consistent terminology; concrete examples.
- [ ] Workflows have clear, ordered steps.
- [ ] Skill is self-contained — no dependency on a registered private
      subagent (roles live in `references/`). *(repo rule — see
      [skills-vs-agents.md](skills-vs-agents.md))*

**Code and scripts**
- [ ] Scripts solve, don't punt; error handling explicit.
- [ ] No unjustified constants.
- [ ] Required packages listed; forward-slash paths only.
- [ ] Validation/feedback loop for critical operations.

**Testing**
- [ ] ≥ 3 evaluations exist.
- [ ] Tested on every model you'll run it on.
- [ ] Tested with real usage, not just synthetic prompts.
