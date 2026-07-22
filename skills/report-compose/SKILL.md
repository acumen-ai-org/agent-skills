---
name: report-compose
description: Generates a single self-contained HTML file that presents arbitrary input content (markdown, JSON, text, docs) with all three view modes baked in — full (scrollable report document with a three-level sidebar), slides (keyboard/click-navigable deck with level-gateway slides), and xr (glasses-style spatial UI with floating panels in dark space). The initial mode is picked by ?mode= querystring; a runtime switcher flips modes in place. Content structures into up to three navigation levels (Areas, Categories, Menu items — any subset works). Accepts an optional DESIGN.md (palette, typography, logo, tone) with an oakai-style mineral-gray default. Runs as two roles: a content role that makes sense of the input, and a fast structure role that assembles and validates the file with deterministic scripts. Use when content needs to become a polished standalone HTML report, presentation, slide deck, or XR/spatial-style page.
---

# report-compose

Turns content into **one .html file** that opens via `file://` on any
machine and carries all three modes — `full`, `slides`, `xr` —
switchable at runtime and pre-selectable with `?mode=`.

The work splits into two roles:

- **Content role** (the session running this Skill — a Sonnet-class
  model): reads the input, decides what matters, designs the structure,
  writes the unit fragments, captions, tokens, and chart code — the
  sense-making. Its deliverable is a **spec directory**
  ([spec-format.md](references/spec-format.md)).
- **Structure role** ([role-structure.md](references/role-structure.md) —
  delegate to an isolated agent on a fast model, e.g. Haiku): turns the
  spec into the output with `scripts/build_report.py`, loops on the
  scripts' error messages until build and validation are green, and
  reports back. The scripts carry the intelligence — they name the file
  and the fix — so the role is mechanical by design.

The template ([references/template.html](references/template.html)) is
the working system: its engine (structure parsing, gateway generation,
mode switching, control enhancement) ships verbatim in every output; the
build splices content, tokens, charts, and the needed CDN tags into it.
No output hand-copies the template.

Reference detail — read when running that step, not before:

- [`references/spec-format.md`](references/spec-format.md) — the spec directory contract
- [`references/structure.md`](references/structure.md) — units, navigation levels, gateways, mode selection
- [`references/mode-full.md`](references/mode-full.md) / [`mode-slides.md`](references/mode-slides.md) / [`mode-xr.md`](references/mode-xr.md) — per-mode rules and open-checks
- [`references/controls.md`](references/controls.md) — the component registry
- [`references/design-input.md`](references/design-input.md) — the DESIGN.md contract
- [`references/DESIGN.md`](references/DESIGN.md) — the default design
- [`references/cdn-libraries.md`](references/cdn-libraries.md) — allowed pinned libraries
- [`references/role-structure.md`](references/role-structure.md) — the structure role

## Inputs

| Input        | Default              | Notes                                                                  |
| ------------ | -------------------- | ---------------------------------------------------------------------- |
| `$CONTENT`   | —                    | Path(s) to content files (markdown, JSON, text), or raw text. Required. |
| `$MODE`      | `full`               | Baked-in default mode when the URL carries no `?mode=`.                |
| `$DESIGN`    | unset → default design | Path to a DESIGN.md. See [design-input.md](references/design-input.md). |
| `$OUT`       | —                    | Output `.html` path. Required.                                          |
| `$TITLE`     | derived from content | Document title.                                                         |
| `$KEEP_SPEC` | `false`              | Keep `<out-stem>.spec/` after a green build (for re-assembly).          |

Requirements: `python3` (standard library only). Opening the result needs
a browser; the pinned CDN libraries need network, the content does not.

## Output contract

- **One `.html` file, three modes.** Every `src`/`href`/`srcset`/CSS
  `url()` is a pinned jsdelivr URL with `integrity` + `crossorigin`, a
  Google Fonts URL (the sole SRI exemption), a `data:` URI, a
  `#fragment`, or `mailto:`. Images and logos are embedded as data URIs.
- **Structure**: units with `data-area`/`data-category`/`data-menu`
  attributes (any subset, used consistently); the engine derives the
  sidebar, gateway slides, and panel sequence. See
  [structure.md](references/structure.md).
- **Provenance**: `<meta name="generator" content="report-compose">`
  plus a visible line with ISO date · source description (authored in the
  cover; the build generates the footer from `report.json`).
- **Graceful degradation**: a network- or script-blocked open loses
  polish, never facts — per-control fallbacks in
  [controls.md](references/controls.md).

`scripts/build_report.py` enforces the spec contract;
`scripts/validate_output.py` enforces the reference and provenance rules.

## Procedure

Track progress:

```
- [ ] 1. Inventory   (content role) — read $CONTENT, list what must appear
- [ ] 2. Structure   (content role) — levels + unit outline per structure.md
- [ ] 3. Design      (content role) — tokens from $DESIGN or the default
- [ ] 4. Author spec (content role) — <out-stem>.spec/: report.json + units/*.html (+ charts.js)
- [ ] 5. Assemble    (structure role, fast model) — build + validate until exit 0
- [ ] 6. Open-check  (content role) — all three modes' check lists
- [ ] 7. Cleanup     — delete the spec dir unless $KEEP_SPEC=true
```

### 1. Inventory

Read every `$CONTENT` file. List what must appear: headline facts,
structures (tables, lists, flows), and anything the reader would miss if
dropped. Everything on the list appears in the output; a deliberate
omission is stated in the output.

### 2. Structure

Read [`references/structure.md`](references/structure.md). Choose the
level depth the content deserves (0–3), name the areas/categories/menu
items, and size units for the slides/xr density rule.

### 3. Design

Read [`references/design-input.md`](references/design-input.md). If
`$DESIGN` is set, derive token overrides and fonts from it; otherwise the
template's defaults apply and `report.json` carries no `tokens`.

### 4. Author spec

Write `<out-stem>.spec/` per
[`references/spec-format.md`](references/spec-format.md): `report.json`,
one fragment per unit under `units/`, `charts.js` when there are `.viz`
figures. Controls follow [controls.md](references/controls.md); mode
rules are in the three mode references. This is the sense-making step —
prose, captions, and numbers are final here.

### 5. Assemble

Delegate to an isolated agent (Agent tool, a fast model such as Haiku):
pass the contents of
[`references/role-structure.md`](references/role-structure.md) as its
instructions with `$SPEC_DIR`, `$SKILL_DIR`, and `$OUT` filled in.
It runs:

```bash
python3 "$SKILL_DIR/scripts/build_report.py" "$SPEC_DIR" "$OUT"
python3 "$SKILL_DIR/scripts/validate_output.py" "$OUT"
```

fixing only what the scripts name, until both exit 0. If it stops on a
content decision (disagreeing levels, a violation needing new prose),
resolve that in the spec yourself and re-delegate. Without an Agent
tool, run the same loop inline.

### 6. Open-check

Open `$OUT` via `file://` (browser tooling if available, otherwise ask
the user), also with `?mode=slides` and `?mode=xr`, and run each mode's
open-check list from its reference file.

### 7. Cleanup

Delete `<out-stem>.spec/` unless `$KEEP_SPEC=true` or a step failed —
the spec is how the caller diagnoses.

## Outputs

`$OUT` — the single HTML file. With `$KEEP_SPEC=true`, also
`<out-stem>.spec/`.

## Failure modes

- **Build exit 2** → spec problems, one per line with file and fix; the
  structure role handles the mechanical ones. Recurring content problems
  (inconsistent levels that neighbors cannot resolve) go back to the
  content role.
- **Build exit 3** → the bundled template lost an anchor — fix
  `references/template.html`, not the spec.
- **Validator exit 3** → usually spec content: a relative href, a missing
  provenance date in the cover. Mechanical fixes belong to the structure
  role; new prose belongs to the content role.
- **Density warnings** → the build warns, never fails; split the flagged
  unit per [structure.md](references/structure.md) or accept deliberately.
- **`$DESIGN` missing or unreadable** → proceed with the default design
  and say so; an absent design is not an error.
- **No network when opening** → expected degradation: diagrams show
  source text, charts and sketches show captions, code is plain. Missing
  facts in this state mean a caption was skipped — fix the spec.
- **No JavaScript** → the file renders as one flowing document; modes and
  navigation need the engine, facts do not.

## Exit codes

`scripts/build_report.py`: `0` built · `1` bad usage · `2` spec invalid
(per-problem list on stderr) · `3` template anchor missing.

`scripts/validate_output.py`: `0` pass · `1` bad usage · `2` file missing
or unreadable · `3` contract violations (one per line on stderr).
