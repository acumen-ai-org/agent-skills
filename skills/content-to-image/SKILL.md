---
name: content-to-image
description: Converts a piece of text into a single explanatory illustration via a 3-step pipeline (extract → art-direct → prompt-synth), then renders it with gpt-image on Azure Foundry or the OpenAI API directly. The art-direct step picks one of 13 functional types via Visme's three-question rule plus a visual-style modifier (line-art / photography / illustration / tactile / isometric / explorative), with optional named themes. Use when an explanatory or hero image is needed from text — standalone or for report hero slots.
---

# content-to-image

Orchestrates a 3-step pipeline, then renders the final image. Each step
follows a **role** in `references/`; the render is a **script**. The Skill is
self-contained — no external registered subagents.

- **Primary axis** — 13 functional types (Statistical, Informational,
  Timeline, How-to, Process, Comparison, List, Location, Flowchart,
  Hierarchical, Anatomical, Geographic, plus Interactive → static runner-up).
- **Secondary axis** — 6 visual-style modifiers. Glass-morphism is the default
  for Illustration / Isometric / Photography / Explorative; Line art and
  Tactile drop it.

Step detail lives in the role files — read them when running that step, not
before:

- [`references/extract.md`](references/extract.md) — step 1 role
- [`references/art-direct.md`](references/art-direct.md) — step 2 role
- [`references/prompt-synth.md`](references/prompt-synth.md) — step 3 role
- [`references/themes.md`](references/themes.md) — the 11 `$THEME` overlays (only if `$THEME` set)

## Inputs

| Input         | Default                                | Notes                                                                                                       |
| ------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `$TEXT`       | —                                      | Path to a text/markdown file, OR raw text. The thing to visualize.                                          |
| `$OUT_DIR`    | `$CLAUDE_PROJECT_DIR/.agents/visuals/` | Where trace files and the PNG land.                                                                          |
| `$SLUG`       | derived from text+timestamp            | Output filename stem.                                                                                        |
| `$TYPE`       | unset → art-direct auto-selects        | Override the primary type.                                                                                   |
| `$STYLE`      | unset → art-direct auto-selects        | Override the visual-style modifier.                                                                          |
| `$THEME`      | unset → no overlay                     | One of the 11 slugs in `references/themes.md`.                                                               |
| `$KEEP_FILES` | `false`                                | `false` deletes the 4 intermediate trace files after the PNG is decoded. `true` keeps them for re-rendering. |

Render env vars (used by `scripts/render.sh`). `IMAGE_PROVIDER` selects the
backend: `foundry` or `openai`. If unset, it defaults to `openai` when
`OPENAI_API_KEY` is set and no Foundry endpoint is configured, else `foundry`.

- **OpenAI** (`IMAGE_PROVIDER=openai`): `OPENAI_API_KEY` (required),
  `OPENAI_IMAGE_MODEL` (default `gpt-image-1`), `OPENAI_BASE_URL`
  (default `https://api.openai.com/v1`). No extra CLI tool needed — it's a
  direct REST call.
- **Azure Foundry** (`IMAGE_PROVIDER=foundry`): `AZURE_FOUNDRY_IMAGE_ENDPOINT`,
  `AZURE_FOUNDRY_IMAGE_DEPLOYMENT` (default `gpt-image-2`), `AZURE_OPENAI_APIKEY`
  (falls back to `az account get-access-token`),
  `AZURE_FOUNDRY_IMAGE_API_VERSION` (default `2025-04-01-preview`).

Requirements: `bash`, `curl`, and `python3` (standard library only — no pip
packages). The `az` CLI is needed *only* for the Foundry path when
`AZURE_OPENAI_APIKEY` is unset; the OpenAI path needs no extra tooling. The
render step makes an outbound HTTPS call.

## Procedure

Track progress:

```
- [ ] 1. Extract      → <slug>.step1-extract.md
- [ ] 2. Art-direct   → <slug>.step2-blueprint.md
- [ ] 3. Prompt-synth → <slug>.brief.md
- [ ] 3b. Theme overlay (only if $THEME set)
- [ ] 4. Render        → <slug>.json
- [ ] 5. Decode        → <slug>.png
- [ ] 6. Cleanup (unless $KEEP_FILES=true)
```

**How to run a step (1–3):** follow the role file's instructions on the step's
input. Run it inline, OR — for fresh, unbiased context — delegate it to an
isolated agent (the Agent tool, `general-purpose`) passing the role file's
contents as the agent's instructions and the step input as the task. Either
way, capture the response verbatim and write it to the named trace file.

### 1. Extract

Input: `$TEXT` (the role reads it if it's a path). Follow
[`references/extract.md`](references/extract.md). Write the response to
`$OUT_DIR/<slug>.step1-extract.md`.

### 2. Art-direct

Input: step 1 output verbatim, plus `$TYPE`/`$STYLE` overrides if set. Follow
[`references/art-direct.md`](references/art-direct.md). Write to
`$OUT_DIR/<slug>.step2-blueprint.md`.

### 3. Prompt-synth

Input: step 2 output verbatim. Follow
[`references/prompt-synth.md`](references/prompt-synth.md). The response is the
final prompt — one continuous text block. Write it verbatim to
`$OUT_DIR/<slug>.brief.md`.

### 3b. Theme overlay (only if `$THEME` set)

If `$THEME` matches a slug in [`references/themes.md`](references/themes.md),
append that row's `AESTHETIC OVERRIDE` block to `<slug>.brief.md` using the
append template there. Skip this step entirely if `$THEME` is unset.

### 4. Render

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/render.sh" "$OUT_DIR/<slug>.brief.md" "$OUT_DIR/<slug>.json"
```

The trailing `HTTP <code>` line reports the status. On non-2xx, stop: keep
`<slug>.json`, surface the error, do not decode.

### 5. Decode

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/decode.py" "$OUT_DIR/<slug>.json" "$OUT_DIR/<slug>.png"
```

Exit 2 means the API returned no image — keep `<slug>.json`, surface it, do
not write a PNG.

### 6. Cleanup (default)

Unless `$KEEP_FILES=true`, delete the four trace files now that the PNG
exists; keep only `<slug>.png`:

```bash
[ "${KEEP_FILES:-false}" = "true" ] || rm -f \
  "$OUT_DIR/<slug>.step1-extract.md" \
  "$OUT_DIR/<slug>.step2-blueprint.md" \
  "$OUT_DIR/<slug>.brief.md" \
  "$OUT_DIR/<slug>.json"
```

Skip cleanup if any step failed — the trace files are how the caller
diagnoses. Set `$KEEP_FILES=true` when iterating on prompts or re-rendering
without re-running the LLM steps.

## Outputs

`$KEEP_FILES=false` (default): `$OUT_DIR/<slug>.png` only.

`$KEEP_FILES=true`: also `<slug>.step1-extract.md`,
`<slug>.step2-blueprint.md`, `<slug>.brief.md` (with theme block if `$THEME`
set), `<slug>.json`. If a step fails, everything written before the failure is
kept regardless of `$KEEP_FILES`.

## Failure modes

- **A step returns malformed output** (missing required sections) → write the
  response anyway, surface a warning, do not proceed. Exit 1.
- **Art-direct picks "Interactive"** → not allowed for static rendering; the
  role's selection rule already promotes the runner-up.
- **Image API non-2xx** → `<slug>.json` written, error surfaced, no PNG. Exit 2.
- **HTTP 401/403** → wrong/missing key for the active provider: `OPENAI_API_KEY`
  (openai) or `AZURE_OPENAI_APIKEY` / `az login` (foundry).
- **API timeout (HTTP 000), Foundry** → confirm `AZURE_FOUNDRY_IMAGE_API_VERSION`
  is `2025-04-01-preview`.
- **Rate limit (HTTP 429)** → ~10/min; for batches > 10, render in waves with
  a 30s sleep between waves.
- **Upstream overload (Foundry "EngineOverloaded", HTTP 429/503, or a body
  mentioning "overloaded"/"capacity")** → handled automatically by
  `render.sh`: a Foundry overload first falls back once to OpenAI if
  `OPENAI_API_KEY` is set, then (if still overloaded or no fallback exists)
  retries the active provider after 5s, 15s, 30s backoff. Only after all of
  these fail does it exit 2 with an upstream-overload message. Non-overload
  errors (auth, bad request, network) are not retried.

## Exit codes

- `0` — image written.
- `1` — a pipeline step failed to return a parseable response.
- `2` — image API failed; trace files were still written.
