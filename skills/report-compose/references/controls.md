# Controls — the component registry

Every visual component an output may use. Each control's markup is shown
in [template.html](template.html) working; copy the shape from there. The
engine (the file's single script) enhances controls at load, before the
initial mode is applied. Anything not in this registry is plain HTML.

Degradation rule for every control: a network-blocked or script-blocked
open loses polish, never facts. Library-rendered controls carry their
facts in a caption or in readable source text.

## Pure CSS (always safe)

| Control | Markup | Notes |
| --- | --- | --- |
| Metric tiles | `.tiles > .tile[.ok/.warn/.error]` with `.num` + `.label` | headline numbers |
| Callouts | `.callout[.ok/.warn/.error]` | one decision/warning/note each |
| Key-value | `.kv > div > dt + dd` | metadata blocks, definition pairs |
| Status chips | `.chip[.ok/.warn/.error]` | inline status labels in text or tables |
| Tables | `.data-table` wrapping `<table>` | numeric cells get `class="num"` |

## Satellite-gated (legal only with declared satellites)

| Control | Markup | Notes |
| --- | --- | --- |
| Page link | `<a class="page-link" href="<out-stem>-pages/<id>.html">Label <span class="hint">what's there</span></a>` | card linking to a declared satellite page ([spec-format.md](spec-format.md)); the build rejects hrefs that don't match a declared satellite, and the validator rejects them without a matching `<link rel="satellite">` |

## Engine-drawn (inline SVG, no library)

| Control | Markup | Notes |
| --- | --- | --- |
| Sparklines | `<span class="spark" data-values="3,5,4,8"></span>` | inline trend in table cells or prose; pair with the end value as text |

## Library-backed (pinned CDN, see [cdn-libraries.md](cdn-libraries.md))

| Control | Markup | Library | Fallback when blocked |
| --- | --- | --- | --- |
| Visualization | `<figure class="viz"><div class="viz-slot" id="..."></div><figcaption>` + a draw call in the engine's chart section | Observable Plot (+ D3) | caption restates the numbers |
| Mermaid diagram | `<figure><pre class="mermaid">source</pre><figcaption>` | Mermaid | diagram source reads as text |
| Code block | `<pre><code class="language-...">` | highlight.js | plain readable code |
| Diff view | `<figure class="diff"><script type="text/x-old">…</script><script type="text/x-new">…</script><figcaption>` | jsdiff | caption summarizes the change; sources kept in a `<details>` when short |
| Excalidraw | `<figure class="excalidraw"><script type="application/json">scene</script><figcaption>` | @excalidraw/utils | caption describes the drawing; scene JSON stays copyable into excalidraw.com |

Visualization guidance: Plot is the default for every chart — line, bar,
dot, area, heatmap (`Plot.cell`). Minimal marks, no decoration, colors
from the design tokens only. One chart per figure; the caption states the
takeaway numbers.

Diff view guidance: the engine renders a side-by-side Before/After view —
removed lines on the left pane (error tint, `−`), added lines on the
right (accent tint, `+`), hatched filler where one side has no
counterpart; never color-alone. Use for code, config, or text changes;
for data changes prefer a table with a delta column.

Excalidraw guidance: for hand-drawn-style concept sketches where Mermaid's
rigid layout fights the idea. The scene JSON is authored (or exported from
excalidraw.com) and embedded; the engine renders it to SVG at load.
Excalidraw's library is the heaviest pin — include its `<script>` tag only
when the report contains a scene.
