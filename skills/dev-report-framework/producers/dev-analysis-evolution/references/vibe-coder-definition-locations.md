# Vibe-coder definition locations

The default search set `collect-author-activity.sh` uses to find a
**repo-defined** "vibe coder" definition, how to point at an external one, and
the rule that the label is only ever assigned from such a definition.

## Default search set

The collector checks these paths in the target repo, in order, and uses the
first that exists and mentions "vibe coder" (case-insensitive):

| Path | What counts |
| ---- | ----------- |
| `docs/vibe-coder.md` | Whole file is the definition. |
| `docs/vibe-coder-definition.md` | Whole file is the definition. |
| `.github/vibe-coder.md` | Whole file is the definition. |
| `CONTRIBUTING.md` | A `## Vibe coder` section (or any "vibe coder" mention). |
| `docs/engineering.md` | A `## Vibe coder` section / mention. |
| `docs/engineering-guidelines.md` | A `## Vibe coder` section / mention. |

The first match's full file text is copied verbatim into the evidence bundle
as `vibe_coder_definition` (`{ path, text }`). No match → `null`.

## Pointing at an external definition

Set `VIBE_CODER_DEFINITION` to a repo-relative path before running
`collect-author-activity.sh`:

```bash
VIBE_CODER_DEFINITION=docs/team/vibe-coder.md \
  bash scripts/collect-author-activity.sh <repo> <out_dir> <ref_range>
```

If the path exists it is used directly (the "mentions vibe coder" check is
skipped — the caller asserted it). If it does not exist the collector falls
back to the default search set.

## The only-from-definition rule

The "vibe coder" label is **only** assigned when a repo-defined definition was
found. The classification role applies that definition's criteria verbatim and
never supplies its own. With no definition:

- the bundle's `vibe_coder_definition` is `null`;
- the `author-activity` fragment omits the `vibe_coders` metric;
- the fragment surfaces the gap as the literal string
  `undetermined — no repository definition found`.

This is the same not-defined-so-surface-the-gap pattern as
`dev-analysis-mission`: the analysis reports the absence as actionable rather
than guessing. A team that wants the column populated adds one of the files
above (a heading or a short paragraph defining their criteria is enough).

## Out of scope

Defining what a "vibe coder" is — that is the repository's call, never this
Skill's. Classifying authors (that is `author-activity-classification.md`).
Rendering.
