#!/usr/bin/env python3
"""Fill a report-compose satellite placeholder with a report fragment.

Usage: render_fragment_page.py <fragment.json> <satellite.html>

Renders a dev-report-fragment/v1 fragment as static HTML into the
placeholder's <main data-page-slot> (written by report-compose's
build_report.py when report.json declares satellites). The page keeps the
placeholder's head contract and design tokens; this script adds a
fragment stylesheet, the rendered sections, and a small sort/filter
behavior for tables. Re-running replaces the previous fill.

Static renderings per section type:
  markdown      minimal GFM subset (headings, lists, fenced code, inline
                code/bold/links)
  table         full row set (children indented), click-to-sort headers,
                substring filter when filterable
  key-value     definition list
  metric-cards  stat tiles
  heatmap       header table, cell shading via color-mix against --accent
  mermaid       diagram source in pre.mermaid + pinned CDN tag + init
  image         <img> (data: URIs pass through)
  diff-view     perspective header rows + before/after cells
  d3-graph, sankey, treemap
                a fallback card naming the type and its node/link/leaf
                counts — interactive layouts stay in the full report

Exit codes:
  0  page filled
  1  bad usage
  2  fragment unreadable or not a fragment object
  3  satellite has no <main data-page-slot>
"""
import html
import json
import pathlib
import re
import sys

MERMAID_TAG = '<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js" integrity="sha384-rbtjAdnIQE/aQJGEgXrVUlMibdfTSa4PQju4HDhN3sR2PmaKFzhEafuePsl9H/9I" crossorigin="anonymous"></script>'

STYLE = """<style id="fragment-styles">
main .fragment-summary { color: var(--muted); max-width: 78ch; }
main section.fragment-section { margin: 2rem 0; }
main section.fragment-section > h2 { font-family: var(--font-serif); font-size: 1.3rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }
main p, main ul, main ol { max-width: 78ch; }
main a { color: var(--accent); }
main code { font-family: var(--font-mono); font-size: 0.9em; }
main pre { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1rem; overflow-x: auto; font-family: var(--font-mono); font-size: 0.84rem; }
main pre.mermaid { text-align: center; }
.frag-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin: 1rem 0; }
.frag-tile { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 1rem; }
.frag-tile .num { font-family: var(--font-mono); font-size: 1.6rem; font-weight: 600; }
.frag-tile .label { color: var(--muted); font-size: 0.82rem; }
.frag-kv { display: grid; grid-template-columns: max-content 1fr; gap: 0.3rem 1.4rem; max-width: 78ch; }
.frag-kv dt { color: var(--muted); font-size: 0.88rem; }
.frag-kv dd { margin: 0; font-family: var(--font-mono); font-size: 0.9rem; }
.frag-filter { min-height: 40px; padding: 0 0.8rem; margin: 0 0 0.6rem; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); font: 0.9rem var(--font-body); width: min(100%, 32rem); }
.frag-table-wrap { overflow-x: auto; }
table.frag-table { border-collapse: collapse; width: 100%; background: var(--surface); font-size: 0.88rem; }
table.frag-table th, table.frag-table td { border: 1px solid var(--border); padding: 0.4rem 0.7rem; text-align: left; vertical-align: top; }
table.frag-table thead th { background: var(--surface-2); position: sticky; top: 0; cursor: pointer; white-space: nowrap; }
table.frag-table thead th::after { content: " ↕"; color: var(--muted); font-size: 0.75em; }
table.frag-table td.num, table.frag-table th.num { text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
table.frag-table td.depth-1 { padding-left: 1.8rem; }
table.frag-table td.depth-2 { padding-left: 3rem; }
table.frag-table td.depth-3 { padding-left: 4.2rem; }
table.frag-heatmap td { text-align: right; font-family: var(--font-mono); }
table.frag-diff td.before del, table.frag-diff td.after ins { text-decoration: none; }
table.frag-diff td.before { background: color-mix(in srgb, var(--error) 10%, transparent); }
table.frag-diff td.after { background: color-mix(in srgb, var(--accent) 10%, transparent); }
table.frag-diff th.perspective { background: var(--surface-2); font-family: var(--font-serif); }
table.frag-diff th.perspective .lead { color: var(--muted); font-weight: 400; font-size: 0.85em; margin-left: 0.6rem; }
main img { max-width: 100%; height: auto; border: 1px solid var(--border); border-radius: 6px; }
.frag-fallback { border: 1px dashed var(--border); border-radius: 8px; padding: 1rem; color: var(--muted); max-width: 78ch; }
</style>"""

BEHAVIOR = """<script id="fragment-behavior">
(function () {
  document.querySelectorAll("table.frag-table").forEach(function (table) {
    var tbody = table.tBodies[0];
    table.tHead.querySelectorAll("th").forEach(function (th, col) {
      var asc = true;
      th.addEventListener("click", function () {
        var numeric = th.dataset.type === "number";
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var x = a.cells[col] ? a.cells[col].textContent.trim() : "";
          var y = b.cells[col] ? b.cells[col].textContent.trim() : "";
          if (numeric) return (parseFloat(x) || 0) - (parseFloat(y) || 0);
          return x.localeCompare(y);
        });
        if (!asc) rows.reverse();
        asc = !asc;
        rows.forEach(function (row) { tbody.appendChild(row); });
      });
    });
  });
  document.querySelectorAll(".frag-filter").forEach(function (input) {
    var table = document.getElementById(input.dataset.target);
    input.addEventListener("input", function () {
      var needle = input.value.toLowerCase();
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        row.style.display = row.textContent.toLowerCase().indexOf(needle) === -1 ? "none" : "";
      });
    });
  });
  if (window.mermaid) mermaid.initialize({ startOnLoad: true, theme: "neutral" });
})();
</script>"""

INLINE_MD = (
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)"), r'<a href="\2">\1</a>'),
)


def md_to_html(md):
    out, para, in_code, in_list = [], [], False, None

    def flush_para():
        if para:
            text = " ".join(para)
            for pattern, repl in INLINE_MD:
                text = pattern.sub(repl, text)
            out.append(f"<p>{text}</p>")
            para.clear()

    def close_list():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    for raw in md.split("\n"):
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para()
            close_list()
            out.append("<pre>" if not in_code else "</pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        stripped = line.strip()
        escaped = html.escape(stripped)
        heading = re.match(r"^(#{1,4})\s+(.*)", stripped)
        bullet = re.match(r"^[-*]\s+(.*)", stripped)
        numbered = re.match(r"^\d+\.\s+(.*)", stripped)
        if heading:
            flush_para()
            close_list()
            level = min(len(heading.group(1)) + 2, 5)
            text = html.escape(heading.group(2))
            for pattern, repl in INLINE_MD:
                text = pattern.sub(repl, text)
            out.append(f"<h{level}>{text}</h{level}>")
        elif bullet or numbered:
            flush_para()
            kind = "ul" if bullet else "ol"
            if in_list != kind:
                close_list()
                out.append(f"<{kind}>")
                in_list = kind
            text = html.escape((bullet or numbered).group(1))
            for pattern, repl in INLINE_MD:
                text = pattern.sub(repl, text)
            out.append(f"<li>{text}</li>")
        elif not stripped:
            flush_para()
            close_list()
        else:
            para.append(escaped)
    flush_para()
    close_list()
    return "\n".join(out)


def esc(value):
    return html.escape(str(value)) if value is not None else ""


def render_table(section, index):
    columns = section.get("columns", [])
    table_id = f"frag-table-{index}"
    parts = []
    if section.get("filterable"):
        parts.append(f'<input class="frag-filter" data-target="{table_id}" type="search" placeholder="Filter rows…">')
    num_class = ' class="num"'
    head = "".join(
        f'<th data-type="{esc(c.get("type", "string"))}"{num_class if c.get("type") == "number" else ""}>{esc(c.get("label", c.get("key")))}</th>'
        for c in columns
    )
    body_rows = []

    def add_rows(rows, depth):
        for row in rows:
            cells = []
            for ci, col in enumerate(columns):
                value = row.get(col.get("key"))
                classes = []
                if col.get("type") == "number":
                    classes.append("num")
                if ci == 0 and depth:
                    classes.append(f"depth-{min(depth, 3)}")
                cls = f' class="{" ".join(classes)}"' if classes else ""
                if col.get("type") == "link" and isinstance(value, dict):
                    cells.append(f'<td{cls}><a href="{esc(value.get("href"))}">{esc(value.get("text", value.get("href")))}</a></td>')
                else:
                    cells.append(f"<td{cls}>{esc(value)}</td>")
            body_rows.append("<tr>" + "".join(cells) + "</tr>")
            add_rows(row.get("children", []), depth + 1)

    add_rows(section.get("rows", []), 0)
    parts.append(
        f'<div class="frag-table-wrap"><table class="frag-table" id="{table_id}">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )
    return "\n".join(parts)


def render_heatmap(section):
    xs = section.get("xLabels", [])
    ys = section.get("yLabels", [])
    cells = {(c.get("x"), c.get("y")): c.get("v") for c in section.get("cells", [])}
    peak = max((abs(v) for v in cells.values() if isinstance(v, (int, float))), default=1) or 1
    head = "<th></th>" + "".join(f'<th scope="col">{esc(x)}</th>' for x in xs)
    rows = []
    for y in ys:
        tds = []
        for x in xs:
            v = cells.get((x, y))
            if v is None:
                tds.append("<td></td>")
            else:
                pct = round(abs(v) / peak * 55)
                tds.append(f'<td style="background: color-mix(in srgb, var(--accent) {pct}%, transparent)" title="{esc(x)} × {esc(y)} = {esc(v)}">{esc(v)}</td>')
        rows.append(f'<tr><th scope="row">{esc(y)}</th>{"".join(tds)}</tr>')
    return f'<div class="frag-table-wrap"><table class="frag-table frag-heatmap"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def render_diff_view(section):
    rows = ['<thead><tr><th>Before</th><th>After</th></tr></thead>']
    body = []
    for persp in section.get("perspectives", []):
        lead = f'<span class="lead">{esc(persp.get("lead"))}</span>' if persp.get("lead") else ""
        body.append(f'<tr><th class="perspective" colspan="2">{esc(persp.get("title"))}{lead}</th></tr>')
        for item in persp.get("items", []):
            before = esc(item.get("before")) or "—"
            after = esc(item.get("after")) or "—"
            body.append(f'<tr><td class="before">{before}</td><td class="after">{after}</td></tr>')
    return f'<div class="frag-table-wrap"><table class="frag-table frag-diff">{rows[0]}<tbody>{"".join(body)}</tbody></table></div>'


def render_section(section, index):
    kind = section.get("type")
    if kind == "markdown":
        return md_to_html(section.get("md", ""))
    if kind == "table":
        return render_table(section, index)
    if kind == "key-value":
        pairs = "".join(f"<dt>{esc(p.get('k'))}</dt><dd>{esc(p.get('v'))}</dd>" for p in section.get("pairs", []))
        return f'<dl class="frag-kv">{pairs}</dl>'
    if kind == "metric-cards":
        cards = "".join(
            f'<div class="frag-tile"><div class="num">{esc(c.get("value"))}{esc(c.get("unit", ""))}</div><div class="label">{esc(c.get("label"))}</div></div>'
            for c in section.get("cards", [])
        )
        return f'<div class="frag-tiles">{cards}</div>'
    if kind == "heatmap":
        return render_heatmap(section)
    if kind == "mermaid":
        return f'<pre class="mermaid">{esc(section.get("diagram"))}</pre>'
    if kind == "image":
        title_attr = f' title="{esc(section.get("title"))}"' if section.get("title") else ""
        return f'<img src="{esc(section.get("src"))}" alt="{esc(section.get("alt"))}"{title_attr}>'
    if kind == "diff-view":
        return render_diff_view(section)
    if kind in ("d3-graph", "sankey"):
        nodes = len(section.get("nodes", []))
        links = len(section.get("links", []))
        return f'<div class="frag-fallback">Interactive {esc(kind)} ({nodes} nodes, {links} links) — the full release report renders it; this page keeps the numbers.</div>'
    if kind == "treemap":
        def leaves(node):
            children = node.get("children", [])
            return sum(leaves(c) for c in children) if children else 1
        return f'<div class="frag-fallback">Interactive treemap ({leaves(section.get("root", {}))} leaves) — the full release report renders it; this page keeps the numbers.</div>'
    return f'<div class="frag-fallback">Unsupported section type <code>{esc(kind)}</code>.</div>'


def main():
    if len(sys.argv) != 3:
        print("usage: render_fragment_page.py <fragment.json> <satellite.html>", file=sys.stderr)
        return 1
    fragment_path = pathlib.Path(sys.argv[1])
    page_path = pathlib.Path(sys.argv[2])
    try:
        fragment = json.loads(fragment_path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"fragment unreadable: {e}", file=sys.stderr)
        return 2
    if not isinstance(fragment, dict) or not isinstance(fragment.get("body"), list):
        print("fragment has no body[] — not a dev-report-fragment object", file=sys.stderr)
        return 2
    try:
        page = page_path.read_text()
    except OSError as e:
        print(f"satellite unreadable: {e}", file=sys.stderr)
        return 2
    slot = re.search(r'(<main data-page-slot="[^"]*">).*?(</main>)', page, re.S)
    if not slot:
        print('satellite has no <main data-page-slot="..."> — not a report-compose placeholder', file=sys.stderr)
        return 3

    sections = []
    if fragment.get("summary"):
        sections.append(f'<p class="fragment-summary">{esc(fragment["summary"])}</p>')
    for i, section in enumerate(fragment["body"]):
        title = f"<h2>{esc(section.get('title'))}</h2>" if section.get("title") else ""
        sections.append(f'<section class="fragment-section">{title}\n{render_section(section, i)}</section>')
    produced = fragment.get("generated_at", "")
    producer = (fragment.get("producer") or {}).get("skill", "")
    if produced or producer:
        sections.append(f'<p class="fragment-summary">Fragment {esc(fragment.get("id"))} · produced by {esc(producer)} · {esc(produced)}</p>')

    filled = page[:slot.start()] + slot.group(1) + "\n" + "\n".join(sections) + "\n" + slot.group(2) + page[slot.end():]
    filled = re.sub(r'<style id="fragment-styles">.*?</style>\n?', "", filled, flags=re.S)
    filled = filled.replace("</head>", STYLE + "\n</head>")
    filled = re.sub(r'<script id="fragment-behavior">.*?</script>\n?', "", filled, flags=re.S)
    needs_mermaid = any(s.get("type") == "mermaid" for s in fragment["body"])
    if needs_mermaid and "mermaid.min.js" not in filled:
        filled = filled.replace("</head>", MERMAID_TAG + "\n</head>")
    filled = filled.replace("</body>", BEHAVIOR + "\n</body>")
    page_path.write_text(filled)
    print(f"{page_path}: {page_path.stat().st_size} bytes, {len(fragment['body'])} section(s) from {fragment_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
