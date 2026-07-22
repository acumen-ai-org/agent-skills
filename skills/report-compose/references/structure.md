# Structure — navigation levels and gateways

Every output is one HTML file with all three modes baked in; this file
defines the content structure both the authoring and the runtime engine
follow.

## Units

The single source of truth is a flat list of `<section class="unit">`
elements inside `<main id="content">`. Each unit is one menu item's
content and declares its place with data attributes:

```html
<section class="unit" id="inputs" data-area="Using the skill"
         data-category="Workflow" data-menu="Inputs">
  <h2>Inputs</h2>
  ...
</section>
```

- `id` — unique slug; the deep-link anchor in every mode.
- `data-menu` — the menu-item label (required on every unit).
- `data-category` — optional middle level.
- `data-area` — optional top level.

The first section is the cover: `<section class="unit cover" id="cover">`
with the title and the provenance line, no data attributes.

## Levels: 0–3

The engine derives the navigation tree from whichever attributes exist:

| Authored attributes | Tree |
| --- | --- |
| `data-area` + `data-category` + `data-menu` | Areas → Categories → Menu items |
| `data-area` + `data-menu` | Areas → Menu items |
| `data-category` + `data-menu` | Categories → Menu items |
| `data-menu` only | Menu items |
| none (cover only, or unlabeled units) | flat document, no nav tree |

Levels must be used consistently: either every unit has `data-area` or
none does, and likewise for `data-category`. Labels group by exact string
match, so consecutive units of one category repeat the same attribute
values.

## What each mode builds from the tree

- **full** — when areas exist, an **area tab bar** on top (one tab per
  area, squared segmented control): the document and the sidebar show only
  the active area; a deep link into another area activates its tab. The
  sidebar lists categories and menu items with scroll-spy; a category
  heading band marks each group in the flow.
- **slides / xr** — a linear sequence: cover, then for each area a
  **gateway**, for each category a **gateway**, then that group's units.

## Gateways

A gateway is a generated slide/panel shown when the sequence enters a new
area or category. It lists all siblings at that level and marks state:
done (already visited in sequence order), current (being entered), and
upcoming. Every entry is a jump target — this is how slides and xr jump
between levels. Gateways exist only for levels the document uses, and
only in slides/xr modes; full mode navigates with the sidebar instead.

## Mode selection and deep links

- `?mode=full|slides|xr` on the URL picks the initial mode (works via
  `file://`); no querystring falls back to the mode baked in as
  `data-default-mode` on `<body>` ($MODE at authoring time, default
  `full`).
- A runtime switcher (fixed, top-right) flips modes; the reader's current
  unit is preserved across the switch. In full mode the switcher shows
  word labels; in slides and xr it shows icons only.
- `#<unit-id>` deep-links to a unit in any mode: full scrolls to it,
  slides/xr open its slide/panel.

## Mode-scoped content

Content identical across modes is the default and the goal. When a block
genuinely cannot work in a projected mode (a 40-row table, a long code
listing), tag it and provide the projection:

- `class="full-only"` — rendered only in full mode.
- `class="deck-only"` — rendered only in slides and xr.

A `full-only` block must have a `deck-only` sibling that carries its
facts (a summary row, a top-5 excerpt) — never drop content from a mode
silently.

## Density (slides and xr)

One idea per unit: at most ~6 bullets, or one figure, or one table of ~6
rows per slide/panel. A unit that outgrows this splits into numbered
units ("Metrics 1/2", "Metrics 2/2") under the same category — never
smaller type.
