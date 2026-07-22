# Spec format — the build input

The spec directory is the handoff between the content role (which writes
it) and the structure role (which builds and validates from it).
`scripts/build_report.py` is the only consumer; its error messages name
the file and the fix.

```
<out-stem>.spec/
├── report.json
├── charts.js        optional
└── units/
    ├── 00-cover.html
    ├── 01-<slug>.html
    └── ...
```

## report.json

```json
{
  "title": "Document title",
  "date": "2026-07-22",
  "source": "one-line description of the input material",
  "default_mode": "full",
  "tokens": { "--accent": "#0e7c66" },
  "fonts_href": "https://fonts.googleapis.com/css2?family=..."
}
```

- `title`, `date` (ISO), `source` — required; `date` and `source` feed the
  generated footer.
- `default_mode` — the no-querystring mode; default `full`.
- `tokens` — optional overrides applied to the template's `:root{}` block;
  every key must already exist there (the build rejects unknown names).
- `fonts_href` — optional replacement Google Fonts CSS2 URL.
- `satellites` — optional `[{"id", "title"}, ...]`; ids kebab-case, unique.
  **The sanctioned exception to the one-file rule**: the build writes one
  placeholder page per entry into `<out-stem>-pages/<id>.html` (same head
  contract and tokens, an empty `<main data-page-slot="<id>">`), injects a
  `<link rel="satellite">` per page into the report head, and legalizes
  `page-link` cards ([controls.md](controls.md)) whose hrefs must match a
  declared satellite exactly. An external data-driven renderer fills the
  placeholders after the build — the report is no longer a single file, and
  that is the point of declaring satellites. Do not declare any unless the
  caller explicitly asked for external pages.

## units/

One file per unit, assembled in filename sort order — number the files
(`00-`, `01-`, …). Each file is exactly one
`<section class="unit" ...>...</section>` fragment following
[structure.md](structure.md):

- `00-*` is the cover: `class="unit cover"`, an `id`, no data attributes,
  carries the title and the visible provenance line (with the ISO date).
- Every other unit: unique `id`; `data-menu` / `data-area` /
  `data-category` each used consistently (all units or none per level).
  A flat document uses no data attributes at all; any use of
  `data-area`/`data-category` makes `data-menu` required.
- Controls inside units follow [controls.md](controls.md); the build
  detects which controls appear and includes only the CDN libraries they
  need.

## charts.js

Present only when units contain `.viz-slot` figures. Plain JavaScript
defining `window.drawCharts` — the build splices it in place of the
template's chart script; the engine calls it once at load.

## Building

```bash
python3 scripts/build_report.py <spec-dir> <out.html>
python3 scripts/validate_output.py <out.html>
```

Build exit codes: `0` built · `1` usage · `2` spec invalid (per-problem
messages) · `3` template anchor missing. Density overflows (too many
bullets or rows for a slide/panel) are warnings, not failures — fix them
by splitting units, or accept them deliberately.
