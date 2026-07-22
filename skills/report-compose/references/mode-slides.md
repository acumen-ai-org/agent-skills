# Mode: slides — navigable deck

One viewport-sized slide at a time. The sequence is derived from the
structure ([structure.md](structure.md)): cover, then per area an area
gateway, per category a category gateway, then that group's units. The
working implementation is [template.html](template.html).

## Navigation contract

- Keys: `→` `Space` `PgDn` advance; `←` `PgUp` back; `Home`/`End` jump.
- Click zones: right 60% advances, left 40% goes back; links, buttons, and
  figures win over the zones.
- `#<unit-id>` tracks the current slide (gateways included); loading with
  a hash opens that slide.
- Gateways are the level-jumping mechanism: every entry is a link, marked
  done (✓) / current (▶) / upcoming (number).
- Chrome: a thin progress bar and a `current / total` counter — nothing
  else.
- `prefers-reduced-motion` disables the slide transition.

## Authoring rules

- Density: one idea per unit — at most ~6 bullets, or one figure, or one
  table of ~6 rows. Overflow splits into numbered units, never smaller
  type (see [structure.md](structure.md)).
- Content that only works in the document flow gets `class="full-only"`
  and a `deck-only` sibling carrying its facts.
- Figure captions restate key numbers — the no-CDN fallback keeps the
  facts.
- The cover doubles as title slide; the last unit should close (summary
  or call to action).

## No-JS fallback

Without JavaScript no mode class is applied and the file renders as one
flowing document — every fact stays readable.

## Open-check

- Keyboard navigates both directions; counter and progress bar track.
- Gateways appear when entering each area/category, with correct
  done/current/upcoming marks, and their entries jump.
- Reloading with `#<unit-id>` restores that slide.
- Zero console errors.
