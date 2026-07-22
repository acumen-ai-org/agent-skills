#!/usr/bin/env python3
"""Assemble a report-compose output from a spec directory.

Usage: build_report.py <spec-dir> <out.html>

Spec directory layout:
  report.json      required: {"title", "date" (YYYY-MM-DD), "source",
                   "default_mode" (full|slides|xr, default full),
                   "tokens" (optional {"--name": "value"}),
                   "fonts_href" (optional Google Fonts CSS2 URL),
                   "satellites" (optional [{"id", "title"}, ...] — the
                   sanctioned single-file exception, see spec-format.md)}
  units/*.html     unit fragments, assembled in filename sort order; each
                   file is exactly one <section class="unit" ...>...</section>;
                   the first must be the cover (class "unit cover", no data
                   attributes); every other unit needs a unique id and
                   data-menu; data-area/data-category are used consistently
                   (all units or none)
  charts.js        optional: replaces the template's chart script; must
                   define window.drawCharts

The build splices the fragments into references/template.html (title,
default mode, tokens, fonts, main content, charts, footer) and keeps only
the CDN library tags whose controls appear in the content:
  pre.mermaid -> mermaid | .viz-slot or charts.js -> d3 + plot
  code.language-* -> highlight.js | figure.diff -> jsdiff
  figure.excalidraw -> excalidraw-utils

When report.json declares "satellites", the build additionally writes one
placeholder page per entry into <out-stem>-pages/ (same head contract and
tokens, an empty <main data-page-slot>), injects one
<link rel="satellite"> per page into the report head, and requires every
a.page-link href in the content to reference a declared satellite. This
deliberately breaks the one-file rule — an external data-driven renderer
takes the placeholders over after the build.

Density warnings (never fatal): a unit with more than 8 <li> or more than
9 <tr> will overflow a slide/panel — split it per structure.md.

Exit codes:
  0  built (path and included libraries on stdout)
  1  bad usage
  2  spec invalid (per-problem messages on stderr)
  3  template anchor missing (template.html was modified incompatibly)
"""
import json
import pathlib
import re
import sys

MODES = ("full", "slides", "xr")
LIBS = (
    ("d3", "/npm/d3@"),
    ("plot", "@observablehq/plot@"),
    ("mermaid", "/npm/mermaid@"),
    ("highlight.js", "highlightjs/cdn-release@"),
    ("jsdiff", "/npm/diff@"),
    ("excalidraw-utils", "@excalidraw/utils@"),
)
SECTION_OPEN_RE = re.compile(r"^<section\s+([^>]*)>", re.S)
ATTR_RE = re.compile(r'([a-zA-Z-]+)="([^"]*)"')


def fail_spec(problems):
    for p in problems:
        print(f"spec: {p}", file=sys.stderr)
    print(f"{len(problems)} problem(s)", file=sys.stderr)
    return 2


def parse_unit(path, text, problems):
    text = text.strip()
    m = SECTION_OPEN_RE.match(text)
    if not m or not text.endswith("</section>"):
        problems.append(f"{path.name}: must be exactly one <section ...>...</section> fragment")
        return None
    attrs = dict(ATTR_RE.findall(m.group(1)))
    classes = attrs.get("class", "").split()
    if "unit" not in classes:
        problems.append(f'{path.name}: <section> must carry class "unit"')
    return {"file": path.name, "text": text, "attrs": attrs, "classes": classes}


def main():
    if len(sys.argv) != 3:
        print("usage: build_report.py <spec-dir> <out.html>", file=sys.stderr)
        return 1
    spec_dir = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])
    template_path = pathlib.Path(__file__).resolve().parent.parent / "references" / "template.html"
    problems = []

    manifest_path = spec_dir / "report.json"
    if not manifest_path.is_file():
        return fail_spec([f"missing {manifest_path}"])
    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return fail_spec([f"report.json: not valid JSON ({e})"])

    title = manifest.get("title", "")
    date = manifest.get("date", "")
    source = manifest.get("source", "")
    default_mode = manifest.get("default_mode", "full")
    tokens = manifest.get("tokens", {}) or {}
    fonts_href = manifest.get("fonts_href", "")
    if not title:
        problems.append('report.json: "title" is required')
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
        problems.append('report.json: "date" must be YYYY-MM-DD')
    if not source:
        problems.append('report.json: "source" is required')
    if default_mode not in MODES:
        problems.append(f'report.json: "default_mode" must be one of {"|".join(MODES)}')
    if fonts_href and not fonts_href.startswith("https://fonts.googleapis.com/css2"):
        problems.append('report.json: "fonts_href" must be a Google Fonts CSS2 URL')
    satellites = manifest.get("satellites", []) or []
    seen_sat = set()
    for sat in satellites:
        sid = sat.get("id", "") if isinstance(sat, dict) else ""
        if not re.fullmatch(r"[a-z0-9-]+", sid):
            problems.append(f'report.json satellites: id "{sid}" must match [a-z0-9-]+')
        elif sid in seen_sat:
            problems.append(f'report.json satellites: duplicate id "{sid}"')
        else:
            seen_sat.add(sid)
        if not (isinstance(sat, dict) and sat.get("title")):
            problems.append(f'report.json satellites: entry "{sid}" needs a "title"')

    unit_files = sorted((spec_dir / "units").glob("*.html")) if (spec_dir / "units").is_dir() else []
    if not unit_files:
        problems.append("units/: no *.html unit fragments found")
        return fail_spec(problems)
    units = []
    for f in unit_files:
        unit = parse_unit(f, f.read_text(), problems)
        if unit:
            units.append(unit)
    if not units:
        return fail_spec(problems)

    ids = {}
    for u in units:
        uid = u["attrs"].get("id", "")
        if not uid:
            problems.append(f'{u["file"]}: missing id attribute')
        elif uid in ids:
            problems.append(f'{u["file"]}: duplicate id "{uid}" (also in {ids[uid]})')
        else:
            ids[uid] = u["file"]
    cover, rest = units[0], units[1:]
    if "cover" not in cover["classes"]:
        problems.append(f'{cover["file"]}: the first unit (filename sort order) must carry class "unit cover"')
    for key in ("data-area", "data-category", "data-menu"):
        if key in cover["attrs"]:
            problems.append(f'{cover["file"]}: the cover must not carry {key}')
    levels_used = any(key in u["attrs"] for u in rest for key in ("data-area", "data-category"))
    for key in ("data-menu", "data-area", "data-category"):
        with_key = [u["file"] for u in rest if key in u["attrs"]]
        required = key == "data-menu" and levels_used
        if (with_key or required) and len(with_key) != len(rest):
            without = [u["file"] for u in rest if key not in u["attrs"]]
            problems.append(f"{key} used inconsistently: missing in {', '.join(without)} (all units or none, see structure.md)")
    if problems:
        return fail_spec(problems)

    for u in rest:
        li = u["text"].count("<li")
        tr = u["text"].count("<tr")
        if li > 8:
            print(f'warning: {u["file"]}: {li} <li> items overflow a slide/panel — split per structure.md', file=sys.stderr)
        if tr > 9:
            print(f'warning: {u["file"]}: {tr} table rows overflow a slide/panel — split or mark full-only per structure.md', file=sys.stderr)

    charts_path = spec_dir / "charts.js"
    charts = charts_path.read_text().strip() if charts_path.is_file() else ""
    if charts and "window.drawCharts" not in charts:
        return fail_spec(["charts.js: must define window.drawCharts"])

    body_all = "\n".join(u["text"] for u in units)
    used = set()
    if "class=\"mermaid\"" in body_all or "class='mermaid'" in body_all:
        used.add("mermaid")
    if "viz-slot" in body_all or charts:
        used.update(("d3", "plot"))
    if "language-" in body_all:
        used.add("highlight.js")
    if 'class="diff"' in body_all:
        used.add("jsdiff")
    if 'class="excalidraw"' in body_all:
        used.add("excalidraw-utils")
    if "viz-slot" in body_all and not charts:
        print("warning: .viz-slot present but no charts.js — chart slots will stay empty", file=sys.stderr)

    pages_dir_name = out_path.stem + "-pages"
    sat_hrefs = {f"{pages_dir_name}/{sat['id']}.html": sat["id"] for sat in satellites}
    linked = set()
    for tag in re.findall(r"<a\b[^>]*>", body_all):
        if "page-link" not in tag:
            continue
        href_match = re.search(r'href="([^"]*)"', tag)
        href = href_match.group(1) if href_match else ""
        if not satellites:
            problems.append(f'page-link "{href}": no "satellites" declared in report.json — page links are only legal with declared satellites')
        elif href not in sat_hrefs:
            problems.append(f'page-link "{href}": must reference a declared satellite ({" | ".join(sorted(sat_hrefs)) or "none"})')
        else:
            linked.add(sat_hrefs[href])
    if problems:
        return fail_spec(problems)
    for sat in satellites:
        if sat["id"] not in linked:
            print(f'warning: satellite "{sat["id"]}" declared but no page-link references it', file=sys.stderr)

    template = template_path.read_text()

    def anchored(pattern, replacement, count=1, flags=0):
        nonlocal template
        new, n = re.subn(pattern, replacement, template, count=count, flags=flags)
        if n == 0:
            print(f"template anchor not found: {pattern}", file=sys.stderr)
            sys.exit(3)
        template = new

    anchored(r"<title>.*?</title>", lambda m: f"<title>{title}</title>", flags=re.S)
    anchored(r'data-default-mode="[a-z]+"', f'data-default-mode="{default_mode}"')
    if fonts_href:
        anchored(r'<link href="https://fonts\.googleapis\.com/css2[^"]*"', lambda m: f'<link href="{fonts_href}"')

    root_match = re.search(r":root \{.*?\n\}", template, re.S)
    if not root_match:
        print("template anchor not found: :root block", file=sys.stderr)
        return 3
    root_block = root_match.group(0)
    for name, value in tokens.items():
        pattern = re.compile(rf"({re.escape(name)}):\s*[^;]+;")
        if not pattern.search(root_block):
            problems.append(f'report.json tokens: unknown token "{name}" (must exist in the template :root block)')
            continue
        root_block = pattern.sub(rf"\1: {value};", root_block)
    if problems:
        return fail_spec(problems)
    template = template.replace(root_match.group(0), root_block)

    for lib, marker in LIBS:
        if lib not in used:
            anchored(rf'<script src="[^"]*{re.escape(marker)}[^"]*"[^>]*></script>\n', "")

    anchored(r'<main id="content">.*?</main>', lambda m: f'<main id="content">\n{body_all}\n</main>', flags=re.S)

    if charts:
        anchored(r"<script>\nwindow\.drawCharts.*?</script>", lambda m: f"<script>\n{charts}\n</script>", flags=re.S)
    else:
        anchored(r"<script>\nwindow\.drawCharts.*?</script>\n", "", flags=re.S)

    lib_list = ", ".join(lib for lib, _ in LIBS if lib in used) or "none"
    footer = (f'<footer class="report">\n  Generated by report-compose on {date} from {source}.\n'
              + (f"  Pinned dependencies: {lib_list} — content remains readable without them.\n" if used else "")
              + "</footer>")
    anchored(r'<footer class="report">.*?</footer>', lambda m: footer, flags=re.S)

    if satellites:
        sat_links = "\n".join(f'<link rel="satellite" href="{pages_dir_name}/{sat["id"]}.html">' for sat in satellites)
        anchored(r'<meta name="generator" content="report-compose">', lambda m: m.group(0) + "\n" + sat_links)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(template)

    if satellites:
        fonts_link = re.search(r'<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">', template).group(0)
        pages_dir = out_path.parent / pages_dir_name
        pages_dir.mkdir(parents=True, exist_ok=True)
        for sat in satellites:
            page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="report-compose">
<title>{sat["title"]} — {title}</title>
<link rel="icon" href="data:,">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{fonts_link}
<style>
{root_block}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-body); font-size: 16px; line-height: 1.6; }}
header.satellite {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 1.3rem clamp(1rem, 3vw, 4rem); display: flex; align-items: baseline; gap: 1.2rem; flex-wrap: wrap; }}
header.satellite h1 {{ font-family: var(--font-serif); font-size: 1.6rem; margin: 0; }}
header.satellite a {{ color: var(--accent); font-size: 0.9rem; }}
main {{ padding: 1.5rem clamp(1rem, 3vw, 4rem); }}
.placeholder-note {{ border: 1px dashed var(--border); border-radius: 8px; padding: 1rem; color: var(--muted); max-width: 78ch; }}
footer.satellite {{ border-top: 1px solid var(--border); color: var(--muted); font-size: 0.85rem; padding: 1rem clamp(1rem, 3vw, 4rem); }}
</style>
</head>
<body>
<header class="satellite"><h1>{sat["title"]}</h1><a href="../{out_path.name}">← {title}</a></header>
<main data-page-slot="{sat["id"]}">
<p class="placeholder-note">Placeholder generated by report-compose on {date} — awaiting its data renderer.</p>
</main>
<footer class="satellite">Satellite page of {out_path.name} · {date} · {source}</footer>
</body>
</html>
"""
            target = pages_dir / f"{sat['id']}.html"
            if target.is_file() and 'class="placeholder-note"' not in target.read_text():
                print(f"satellite {sat['id']}.html: kept — already filled by its renderer", file=sys.stderr)
            else:
                target.write_text(page)

    sat_note = f", satellites: {len(satellites)} page(s) in {pages_dir_name}/" if satellites else ""
    print(f"{out_path}: {out_path.stat().st_size} bytes, {len(units)} unit(s), libraries: {lib_list}{sat_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
