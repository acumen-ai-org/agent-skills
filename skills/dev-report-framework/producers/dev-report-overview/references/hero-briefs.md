# Role: Per-sub-section hero briefs

Recommended model: any model the visual-brief mechanics support — this writes
one short scene brief per Overview sub-section for `content-to-image`.

Each Overview sub-section (Summary, Diff view, Changes, Shifts) gets an
editorial hero illustration whose spatial metaphor matches the sub-section's
structural kind. You produce one brief per sub-section; the Procedure feeds
each to `content-to-image` and records the resulting image path into
`overview-extras.json.images`.

## Contents

- [When invoked](#when-invoked)
- [TYPE per sub-section](#type-per-sub-section)
- [Style / theme](#style--theme)
- [Slugs](#slugs)
- [Scrub](#scrub)
- [Opt-out](#opt-out)
- [Fallback](#fallback)
- [Out of scope](#out-of-scope)

## When invoked

After `change-shift-narrative` produced the change bullets and shift rows, so
each sub-section's substance is known. One brief per non-empty sub-section.

## TYPE per sub-section

TYPE drives the spatial metaphor, not the aesthetic:

| Sub-section | TYPE |
|---|---|
| Summary | `informational` |
| Diff view | `comparison` |
| Changes — mostly features | `informational` |
| Changes — mostly fixes | `comparison` |
| Shifts | `comparison` |
| unknown | `informational` |

Diff view and Shifts are inherent deltas — their hero reads literally as a
before/after.

## Style / theme

`isometric` plus a restrained editorial theme, pinned across every hero so the
whole report belongs to one publication. TYPE controls layout; style never
varies per sub-section. House overlay: editorial isometric, restrained
palette, 16:10, no text, logos, faces, UI chrome, or code. Use named
real-world objects, verbs of motion, and spatial relationships — zero software
nouns, no "glowing X" wallpaper.

## Slugs

Stable across runs so the content-to-image cache hits release over release:

| Sub-section | slug |
|---|---|
| Summary | `overview-summary` |
| Diff view | `overview-diff` |
| Changes | `overview-changes` |
| Shifts | `overview-shifts` |

The Procedure maps each rendered image to the matching `images` key
(`summary`, `diff-view`, `changes`, `shifts`).

## Scrub

Strip PII and secret-shaped strings (tokens, keys, emails, internal hostnames)
from a brief before sending. Never name a product, company, or internal
module.

## Opt-out

Honor a `DEV_REPORT_NO_IMAGES=1`-style opt-out: when set, every hero is
content-to-image's guaranteed fallback tile instead of a generated image. The
opt-out never blocks the build — `to-fragment.py` still emits the sub-sections,
just without a hero image (or with the fallback tile recorded).

## Fallback

If a text→visual-brief role is unavailable, fall back to the legacy ad-hoc
scene-translation rules in
`inspiration_dev-work-report/prompts/legacy-translation-rules.md` (named
objects, verbs of motion, spatial relationships, zero software nouns). A
provider failure still yields content-to-image's guaranteed fallback tile; the
report ships either way.

## Out of scope

Rendering (that is `content-to-image`). Placing the image or assigning its
menu (`to-fragment.py` does that from the `images` keys). Change/shift
classification (`classify-changes.py`) or the prose
(`change-shift-narrative`).
