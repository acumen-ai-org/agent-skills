# Themes registry

Loaded only when the Skill is invoked with `$THEME` set. Eleven named
palette/mood overlays. Applied as an `AESTHETIC OVERRIDE` block appended to the
brief between the prompt-synth output and the render call. Each block tells the
image model to apply the theme's palette / texture / mood while preserving
spatial layout and verbatim text.

## Contents

- [Registry](#registry)
- [Append template](#append-template)

## Registry

| Slug                | Label                                     | Override directive (verbatim)                                                                                                                                                                                                                                            |
| ------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `elegant-editorial` | Elegant, premium, and editorial           | Use a refined editorial palette: ivory or warm-cream background, charcoal type, deep navy and burnished gold accents, generous negative space, classic serif typography, magazine-grade restraint. No glass-morphism, no neon glow.                                      |
| `retro-muted`       | Retro-inspired with muted tones           | Use a 1970s-inspired muted palette: dusty mustard, faded terracotta, sage, warm cream, soft brown. Slight grain texture. Soft rounded geometry. No glass-morphism, no neon, no deep navy gradient.                                                                       |
| `bright-minimal`    | Bright, modern, and minimal               | Use a bright minimal palette: pure white background, large blocks of saturated primaries (cobalt blue, signal red, lemon yellow), thin precise black strokes, abundant white space. Flat, no gradients, no glass-morphism.                                               |
| `dark-dramatic`     | Dark mode, high-contrast, and dramatic    | Use a near-black background, high-contrast white and electric cyan strokes, vivid magenta or amber accents, strong shadows and rim lighting. Dense moody atmosphere. Glass-morphism allowed but with deep shadow and high contrast.                                      |
| `nature-organic`    | Nature-inspired with organic tones        | Use earthy organic tones: forest green, moss, terracotta, bark, sky-pale, ochre. Hand-drawn organic shapes, leaf and stone textures, paper grain. No digital glass-morphism, no neon.                                                                                    |
| `futuristic-sleek`  | Futuristic, tech-driven, and sleek        | Use a sleek tech palette: gunmetal and obsidian gradients, electric cyan (#00E5FF) and laser-violet accents, ultra-thin geometric line work, holographic chrome highlights. Glass-morphism with sharp HUD-style edges.                                                   |
| `space-glow`        | Space-themed with deep contrast and glow  | Use a deep-space palette: midnight indigo to obsidian background, distant star field, nebula magenta and teal glows, luminous edge halos around every shape, soft bloom. High contrast between black void and luminous accents.                                          |
| `vibrant-gradient`  | Vibrant gradient-based and modern         | Use bold modern gradients: electric blue → fuchsia → orange flowing across surfaces, saturated and high-energy, soft blur transitions, modern sans-serif type. Replace flat fills with gradient fills throughout.                                                        |
| `hand-drawn`        | Hand-drawn, sketch-style, and human       | Render entirely as a hand-drawn sketch on textured cream paper: pencil and ink line work, slight imperfect strokes, hand-lettered labels, watercolor washes for fills, visible paper grain. NO glass-morphism, NO digital gradient, NO neon.                             |
| `luxury`            | Luxury brand aesthetic                    | Use a luxury palette: deep matte black or graphite background, brushed gold and champagne accents, ivory type, very subtle tonal contrast, refined thin serif typography, embossed-feel ornament. No saturated color, no neon. Quiet and exclusive.                      |
| `high-energy`       | High-energy, dynamic, and motion-inspired | Convey motion: diagonal action lines, speed streaks, subtle motion blur on edges, vivid contrasting accents (electric red, cyan, white), kinetic typography. Layout still readable but everything feels mid-motion. Glass-morphism allowed but tilted on dynamic angles. |

## Append template

Substitute `<label>` and `<directive>` from the matching row, then append the
block to the brief before rendering:

```
AESTHETIC OVERRIDE — apply this theme throughout the image: "<label>". <directive> Replace any references to default palette tokens with theme-appropriate equivalents. Preserve every spatial layout instruction, every region label, and every verbatim quoted text exactly as written above. The theme controls palette, texture, mood, and finish; the structural directives control composition.
```

If `$THEME` is unset, this file is not consulted and no override block is
appended.
