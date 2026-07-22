# Default design — mineral gray, one green accent

The design used when the caller provides no `$DESIGN`. A quiet instrument:
warm mineral gray field, near-black text with a green undertone, and one
deep moss accent spent only where the report has something to say. Rust is
the counter-color for errors and removals. Nothing decorative; every color
carries meaning.

## Palette

- Background: warm mineral gray `#F1F1EE`
- Surface (cards, panels): `#FBFBF9`
- Muted surface / dividers: `#E3E5DF`
- Text: `#22261F` (near-black, green undertone)
- Secondary text and labels: `#757D6E`
- Accent: deep moss `#3F5233` — links, primary emphasis, the "settled" signal
- Accent tint: `#E7ECE0` — selected states, subtle highlights
- OK: moss `#3F5233`
- Warning: dry ochre `#9A6B1F`
- Error / removed: rust `#8C4A32`, tint `#F0E4DD`
- Added (diffs): moss on `#E7ECE0`; removed: rust on `#F0E4DD`

Status is never color-alone — always paired with a label.

## Typography

- Headings and ledes: Newsreader (Google Fonts), fallback Georgia — the
  content reads like print
- Body and UI: Inter, fallback system sans
- Numbers, keys, code: IBM Plex Mono, fallback monospace, `tabular-nums`
  for anything a reader compares

## Tone

Formal, third person, no exclamation marks. Labels sentence-case; small
labels may be uppercase with wide tracking.

## Density

Comfortable. `1px` hairline borders, `6px` radius on surfaces, no drop
shadows except floating chrome (mode switcher, rails).

## XR adaptation

In xr mode the field inverts to deep space (see
[mode-xr.md](mode-xr.md)): background `#07080a`-family, translucent dark
panels, text at ~92% white. The accent lifts to a legible moss
(`#9dbe86`-family) and rust lifts likewise; everything else above still
applies.
