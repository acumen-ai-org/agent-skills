# Pattern: behavior-shape before/after mermaid pair

A way to make an architectural, security, or schema shift legible at a glance
using the framework's permanent two-column layout — no contract or renderer
change. It targets **analysis producers** that already emit `mermaid` or
describe a delta (`dev-analysis-architecture`, `dev-analysis-schema`, and the
`Shifts` section of `dev-report-overview`). It is **not** for the
single-column Overview synthesis areas (`Summary`, `Diff view`, `Changes`).

## The shape

A before/after pair is two `mermaid` sections at the **same level of
abstraction**:

- the prior shape as `{ "type": "mermaid", "view": "production", "menu": "<G>", … }`
  (lands in the right **vs production** column), and
- the new shape as `{ "type": "mermaid", "view": "release", "menu": "<G>", … }`
  (lands in the left **This release** column),

with the **same** `menu` label `<G>` so they pair under one top-menu entry of
the producer's own area (e.g. architecture's `C4`, schema's `Changes`). It
adds no entry to the Overview menu. The renderer places the two columns side
by side automatically; there is no custom layout.

## Authoring rules

- Both diagrams use the **same diagram type and the same node granularity** so
  the delta reads as a visual difference, not a textual one.
- Describe **behavior or shape**, never raw diff lines or file names. Example:
  a prior "auth reads JWT from a cookie" flow versus a new "auth reads the
  `Authorization` header and validates the `aud` claim" flow — the same three
  nodes, one edge and one check changed.
- Keep the two diagrams comparable: same direction, same labels for unchanged
  nodes, only the changed part differs.
- Every emitted diagram MUST pass `scripts/verify_mermaid.py` before the
  fragment is written (the same Layer-1 lint the validator gates on; run the
  standalone tool as a producer self-test to also get the optional deep
  parse). A malformed "before" then fails the build instead of rendering as
  one blank panel next to a good one.

## When there is no meaningful prior shape

For a genuinely new capability there is no honest "before". Emit **only** the
`release` diagram. The framework and `dev-report-vs-production` render the
standard empty-production-column text (`No previous production to compare
with`, or `— nothing for this view —` when a baseline exists) on their own.
Never fabricate a fake "before" and never emit a placeholder diagram — the
absence is the signal, and the renderer owns the message.

## Generation is a role step

Producing the two diagrams is an LLM **role step** documented in the
producer's own SKILL — it reasons about the shift and writes the two diagram
strings. The producer's `to-fragment.py` only places them into the two `view`
slots and runs the mermaid check; it never calls a model and carries no
comments. The pair is plain framework content: no new body type, no renderer
change, no Overview menu entry.
