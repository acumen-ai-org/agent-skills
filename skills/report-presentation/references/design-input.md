# Design input — the DESIGN.md contract

`$DESIGN` is an optional markdown file describing the desired look. It is
prose the model interprets, not a parsed format — headings below are
conventions, not required syntax. Every section is optional.

When `$DESIGN` is absent, the default design applies:
[`references/DESIGN.md`](DESIGN.md) — mineral gray field, deep moss
accent, rust counter-color, Newsreader/Inter/IBM Plex Mono. The
`template.html` token block implements it.

Explicit values (hex colors, font names) are honored verbatim. Everything
not specified is derived coherently from what is: a stated accent color
tints borders, links, and selected states; a stated dark background
raises text contrast and lightens surfaces relative to it.

## Sections and what they feed

| Section | Feeds | Fallback when absent |
| --- | --- | --- |
| Palette | the `:root{}` tokens `--bg --surface --surface-2 --border --text --muted --accent --accent-veil --ok --warn --error --error-veil` | the default design's values |
| Typography | serif/body/mono font stacks; Google Fonts CSS2 link allowed (see [cdn-libraries.md](cdn-libraries.md)) | Newsreader / Inter / IBM Plex Mono |
| Logo | cover/header `<img>` embedded as a data URI, or inline SVG | omitted |
| Tone | microcopy, heading voice (formal vs. conversational) | formal, third person |
| Density | spacing scale: comfortable or compact | comfortable |

## Rules

- All theme colors land in the single `:root{}` block — the only place
  hex values appear in an output (the `body.mode-xr` override block and
  the fixed figure-card values are part of the template's contract, not
  the theme).
- Contrast: text-on-surface pairs must hold WCAG AA (4.5:1 body, 3:1
  large). If an honored verbatim value breaks that, adjust the *other*
  side of the pair and keep the stated value.
- Logo files are read and embedded as `data:` URIs. If the file is missing
  or unreadable, omit the logo and say so in the provenance line — never a
  broken `<img>`.

## XR constraint

The `body.mode-xr` token overrides keep the deep-space background and
panel structure regardless of palette; a DESIGN.md contributes the accent
(lifted to stay legible on dark), typography, and at most a tint of the
panel surfaces. See [mode-xr.md](mode-xr.md).

## Sample DESIGN.md

```markdown
# Design — Acme Q3 review

## Palette
- Accent: #0E7C66
- Background: warm off-white (#FAF8F4)
- Status colors: default green/amber/red are fine

## Typography
- Headings: Fraunces (Google Fonts), fallback Georgia
- Body: Inter, fallback system sans
- Code: JetBrains Mono, fallback monospace

## Logo
- assets/acme-mark.svg, top-left of the cover, max height 32px

## Tone
- Formal, third person, no exclamation marks

## Density
- Comfortable — read on large screens in meetings
```
