# Role: Deck assembly

You assemble one Slidev `slides.md` from the synthesized perspectives. You
receive, per admitted perspective (from
[`perspective-discovery.md`](perspective-discovery.md)), its narrative, its
PNG path, and the deck-level facts. You write the markdown only; building the
deck is `scripts/build-deck.sh`.

## Contents

- [When invoked](#when-invoked)
- [Inputs](#inputs)
- [Slidev structure](#slidev-structure)
- [Slide template](#slide-template)
- [Output](#output)
- [Hard rules](#hard-rules)
- [Out of scope](#out-of-scope)

## When invoked

After every admitted perspective has been synthesized
([`perspective-synthesis.md`](perspective-synthesis.md)) and its
`content-to-image` PNG written (except a mission `status: info` slide, which
has no PNG). Run once per deck.

## Inputs

- Per perspective: name, narrative (≤120 words), PNG path or `NO-IMAGE`,
  `status` of its fact source (`ok|info|warn|error`).
- Deck facts: repo, `range`, `ref_a`, `ref_b` from `diff-facts.json`.

## Slidev structure

`slides.md` is one Slidev markdown file. Slides are separated by a line
containing only `---`. Front-matter is the first block.

1. **Title slide** — front-matter `theme: default`, then an `H1` of the repo
   name + the release range, an `H2` of `ref_a → ref_b`, and a one-line
   generated-at note.
2. **One slide per perspective**, in discovery order. Layout `image-right`
   with the PNG as the slide image and the narrative as the slide body under
   an `H2` of the perspective name. A mission `status: info` slide uses the
   default layout (no image) and renders the reflection questions as the body.
3. **Closing risk-summary slide** — `H2` "Release risk summary", then a
   markdown table of every perspective and the `status` of its fact source,
   plus a one-line roll-up: the worst status across perspectives drives the
   headline (`error` → "Blocking findings", `warn` → "Review required",
   else "No blocking findings").

## Slide template

Title slide:

```
---
theme: default
title: <repo> release diff <ref_a> → <ref_b>
---

# <repo>

## <ref_a> → <ref_b>

Generated <ISO-8601 UTC>
```

Per-perspective slide:

```
---
layout: image-right
image: <png-path>
---

## <Perspective name>

<narrative prose, ≤120 words>
```

Mission `status: info` slide (no image):

```
---
---

## Mission alignment

<reflection questions as a markdown list, verbatim from the mission fragment>
```

Closing slide:

```
---
---

## Release risk summary

| Perspective | Status |
|-------------|--------|
| <name>      | <status> |
| ...         | ...      |

<roll-up line>
```

## Output

Output only — the complete `slides.md` content, nothing else. No commentary
before or after.

## Hard rules

- Output only — the verbatim `slides.md` file content.
- Slide separator is a line of exactly `---`.
- One slide per admitted perspective, discovery order, image-right except the
  mission `status: info` slide.
- Closing slide's roll-up uses the worst `status` across perspectives.
- Forward-slash paths only.

## Out of scope

Building or serving the deck (`scripts/build-deck.sh` runs Slidev). Choosing
or synthesizing perspectives (the other roles). Generating images
(`content-to-image`).
