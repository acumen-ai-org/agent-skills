# Reading the release overview

This is the report's landing page — the one fragment that summarizes every
other. It is pinned first and is the default page on load. It does not analyze
the codebase itself; it rolls up what the producers found.

## What to look for

- **The infographic.** A one-shot illustration of the release scope. It is
  context, not data — the numbers live in `metrics` and in each producer's own
  fragment. If the image backend was unavailable the overview ships without it;
  the bullets still carry the scope.
- **Release-scope bullets.** The high-level shape of the release: what changed,
  the headline risks, where to look next. Each bullet points at a producer
  fragment that holds the detail.
- **Rollup metrics.** Fragment count, one count per status (`ok`, `info`,
  `warn`, `error`), and the commit / scope total. These are the diff surface —
  the split-screen compares them release over release.

When the Overview carries the extended summary, its top menu is
`Summary · Diff view · Changes · Shifts`:

- **Summary.** The infographic and scope bullets above — the release at a
  glance and pointers into the producer fragments.
- **Diff view.** A before/after word-diff grouped by perspective (user, arch,
  product, and — when configured — workflow). Empty `before` means new; empty
  `after` means removed; both means changed. Read it for *what a reviewer
  actually sees differently*, not file churn.
- **Changes.** The release's commits grouped by a single primary change type
  (feature, bugfix, refactor, …) with a count and a few bullets per group.
  Read it for the shape of the release at the commit level.
- **Shifts.** Architectural and technical signals that fired (auth, public
  API, schema, dependencies, config, …) with the affected modules. A `warn`
  status here means a breaking, security, or public-API shift fired — open it
  first.

## What it means

- **The overview is downstream of everything.** It is generated after every
  producer has staged its fragment. If a count looks low, a producer ran late,
  not that the work was missing.
- **The headline status is the worst present.** `error` beats `warn` beats
  `info` beats `ok`. One failing producer drives the overview to `error` even
  when most are clean — open that producer to see why.
- **Bullets summarize, they don't replace.** Treat each bullet as a pointer:
  the authoritative numbers and tables are in the producer fragment it names.
- **A missing image is a degrade, not a failure.** The release still shipped
  its overview; only the illustration is absent.

## Status

The overview's status mirrors the worst producer status in the release. Read
it as the one-line health line for the whole report, then drill into whichever
producer set it.
