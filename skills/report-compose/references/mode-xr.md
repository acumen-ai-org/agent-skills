# Mode: xr — glasses-UI presentation

A spatial-UI visual language in ordinary HTML: the same sequence as
slides (gateways included, [structure.md](structure.md)), but as floating
panels in dark space with snap scrolling — the way Android XR and
visionOS environments present flat surfaces. No WebXR APIs, no 3D
runtime; glasses browsers are the eventual target, so everything is built
for distance reading and coarse pointing. The working implementation is
[template.html](template.html).

## Space

- The mode overrides the design tokens on `body.mode-xr`: near-black deep
  space (`#07080a`-family, never pure `#000`) with a subtle radial
  vignette; the accent lifts to a legible tint of the design's accent.
- One focus target at a time: vertical CSS scroll snapping settles each
  panel centered in view, with large gaps between panels.

## Panels

- Each unit's body becomes the panel: semi-translucent dark fill,
  `backdrop-filter: blur`, radius 24–32px, 1px light border, soft outer
  glow, padding 32–48px, max-width ~820px, centered.
- Figures (charts, mermaid, diffs, sketches, tables) sit on their light
  figure card inside the panel — rendered once, readable in every mode.
- Density rules are the slides rules.

## Type and contrast

- Body ≥ 18px, generous line-height; text ~92% white, secondary ~60%.
  Every text/panel pair holds WCAG AA (4.5:1 body, 3:1 large).

## Chrome and interaction

- A dot rail (right edge) is the only persistent navigation: one dot per
  sequence entry, gateway dots outlined and slightly larger, current dot
  filled with the accent. Dots and gateway entries are the jump targets.
- All interactive targets ≥ 48px or outlined focus rings.
- Motion: panels settle on entry only; `prefers-reduced-motion` disables
  it.

## Theming under DESIGN.md

The dark space and panel structure are the mode, not the theme
([design-input.md](design-input.md)): a DESIGN.md contributes accent,
typography, and at most a tint of the panel fill. A light palette does
not make an XR page light.

## Open-check

- Dark space with floating panels; scroll snaps panel-per-panel.
- Rail tracks the centered panel; gateway dots are distinguishable.
- Body text ≥ 18px; no horizontal scroll at any width.
- Zero console errors.
