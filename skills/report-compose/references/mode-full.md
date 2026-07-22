# Mode: full — scrollable report document

The reading mode: one continuous document with a sidebar for jumping.
Structure and units are defined in [structure.md](structure.md); the
working implementation is [template.html](template.html).

## What the engine builds in this mode

- **Area tabs** (sticky, top — only when areas exist): one squared tab
  per area; the active tab filters the document and the sidebar to that
  area, and clicking a tab jumps to its first unit. Deep links into
  another area activate its tab.
- **Sidebar** (sticky, left): category labels and menu-item links for the
  active area. Scroll-spy highlights the unit in view. Collapses above
  the content below 960px.
- **Bands**: a category band injected where each group starts, so the
  document reads with its structure visible.
- Gateways are hidden — tabs and the sidebar are this mode's navigation.

## Authoring rules

- The cover unit renders as the document header: title, lede, provenance
  line.
- The layout uses the full viewport width (fluid gutters, sidebar fixed);
  prose stays at ~78ch measure while tables, diagrams, and charts may
  span the whole content column. Below 960px the sidebar collapses above
  the content. A document with no navigation tree drops the sidebar
  column entirely.
- Each unit starts with an `<h2>`.
- Order units by what the reader needs first, not by input file order.
- Everything in `$CONTENT` appears somewhere; a deliberate omission is
  stated in the report.
- JSON input: surface what a reader cares about — headline numbers as
  tiles, lists as tables, statuses as chips or callouts. Raw dumps only
  inside a collapsed `<details>`, and only when the data resists summary.
- The footer (full mode only) carries the generated-by line and the pinned
  CDN dependency list.

## Open-check

- Area tabs (when areas exist) switch and filter the document and
  sidebar; a hash link into another area activates its tab.
- Every sidebar link jumps to its unit and the scroll-spy follows.
- Category bands appear at each group boundary.
- Diagrams, charts, diffs, and sketches render.
- Zero console errors.
