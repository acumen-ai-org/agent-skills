# Allowed CDN libraries

The only external references an output file may carry. Everything else —
content, CSS, JS glue, images — is embedded in the file. Include only the
libraries the content actually uses (see the control-to-library mapping in
[controls.md](controls.md)).

## Pinned libraries

| Library | Purpose | Tag to copy |
| --- | --- | --- |
| D3 7.9.0 | required by Plot, load first | `<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js" integrity="sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i" crossorigin="anonymous"></script>` |
| Observable Plot 0.6.17 | visualizations | `<script src="https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/dist/plot.umd.min.js" integrity="sha384-JUpn2GgRr0gxU0xOBd8D8P634jhRCwobtG8G2MMEkX1RnGJ7/FJNnuukpfT+H2w1" crossorigin="anonymous"></script>` |
| Mermaid 11.4.1 | diagrams | `<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js" integrity="sha384-rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I" crossorigin="anonymous"></script>` |
| highlight.js 11.10.0 | code highlighting | `<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.10.0/build/highlight.min.js" integrity="sha384-GdEWAbCjn+ghjX0gLx7/N1hyTVmPAjdC2OvoAA0RyNcAOhqwtT8qnbCxWle2+uJX" crossorigin="anonymous"></script>` |
| jsdiff 7.0.0 | diff views | `<script src="https://cdn.jsdelivr.net/npm/diff@7.0.0/dist/diff.min.js" integrity="sha384-UeyWE2TKK+s95khAzg8xeTD88VbztEqt1mbxzkzwAPM32TPJSj8Lyg7E7tVXAyRL" crossorigin="anonymous"></script>` |
| Excalidraw utils 0.1.2 | Excalidraw scene → SVG | `<script src="https://cdn.jsdelivr.net/npm/@excalidraw/utils@0.1.2/dist/excalidraw-utils.min.js" integrity="sha384-PKzoxe86QGVlqsE3fJ2YdWcVokf/EDKiaR0xFa8W3pzMltvDYh9VQD2KfEcNnKId" crossorigin="anonymous"></script>` |

Excalidraw utils is ~1.5 MB — the heaviest pin by far. Include it only
when the report embeds a scene.

## Google Fonts exemption

`fonts.googleapis.com` / `fonts.gstatic.com` links are the only allowed
references without SRI (the CSS2 endpoint serves per-browser responses, so
a stable hash is impossible). Load fonts via one `<link rel="stylesheet">`
to the CSS2 endpoint; system font stacks are the no-network fallback.

## Rules

- **Copy the whole tag from this table or the template — never retype a
  URL or hash.** A typo in either silently breaks the library under SRI.
- Adding or bumping a library means updating this table, `template.html`,
  and recomputing the hash — in the same change.
- Compute an SRI hash with:
  `curl -s <url> | openssl dgst -sha384 -binary | openssl base64 -A`
- Every library must degrade gracefully — see the per-control fallback
  column in [controls.md](controls.md).

## Rejected libraries

Decided against, so it is not relitigated per output:

- **Chart.js** — replaced by Observable Plot: Plot's defaults are the
  minimalistic, clear statistical graphics this skill wants, with a
  smaller authored-code surface per chart.
- **Alpine / htmx / any framework** — the engine is a few hundred lines of
  vanilla JS; a framework adds a dependency for no capability.
- **Tailwind CDN** — runtime CSS generation in a static artifact; all
  styling lives in the file's single `<style>` block.
