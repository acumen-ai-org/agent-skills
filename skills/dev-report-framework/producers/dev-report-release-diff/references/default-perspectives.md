# Default perspectives

The curated perspective set for a release-diff deck. Each perspective binds to
one static fact source and one `content-to-image` `$TYPE` hint. A perspective
is included in the deck **only when its fact source produced data**; an empty
or absent source drops the slide (the discovery rule —
[`perspective-discovery.md`](perspective-discovery.md)).

`$TYPE` is one of the 13 `content-to-image` functional types. It is a hint:
`content-to-image`'s art-direct step may override it, but passing it biases the
illustration toward the right structure for the perspective's data shape.

## The curated 8

| # | Perspective | Fact source | `$TYPE` hint | Included when |
| - | ----------- | ----------- | ------------ | ------------- |
| 1 | Architecture impact | `dev-analysis-architecture` graph + `collect-diff.sh` `diff.by_extension` / module spread | Hierarchical | An architecture fragment exists, or the diff touched ≥ 2 top-level modules. |
| 2 | API & contract surface | `dev-analysis-schema` `schema-diff.json` (`collect-diff.sh` `schema.*`) | Comparison | `schema.total_changes > 0` (a real contract change exists). |
| 3 | Data & schema changes | `dev-analysis-schema` MCP/struct diff + diff facts for `*.sql`/migration/fixture paths | Anatomical | Schema diff present, or migration/fixture/seed paths changed. |
| 4 | Security & attack surface | `dev-analysis-security` fragment (network/secrets) | Flowchart | A security fragment exists with `status` `warn`/`error`, or new egress/auth paths changed. |
| 5 | Dependency & supply-chain | `dev-analysis-dependencies` fragment (CVE/license rollup) | Statistical | A dependencies fragment exists. |
| 6 | Test coverage & risk | `dev-test-contracts` / `dev-analysis-quality` fragment | Statistical | A contracts or quality fragment exists. |
| 7 | Performance & resource | `dev-analysis-quality` complexity/LOC delta (`scc`) + diff size | Statistical | A quality fragment with complexity metrics exists. |
| 8 | Operational & observability | `dev-analysis-security` egress inventory + diff facts for ops/IaC/config paths | Process | Config/IaC/manifest/observability paths changed, or an ops-relevant fragment exists. |

## The conditional 9th — mission alignment

| Perspective | Fact source | `$TYPE` hint | Included when |
| ----------- | ----------- | ------------ | ------------- |
| Mission alignment | `dev-analysis-mission` fragment | Informational | **Always present as a slide.** When mission docs were found (`status` `ok`/`warn`), the slide is the alignment narrative + image. When no docs were found (`status: info`), the slide instead presents the reflection questions from the mission fragment's `body[]` verbatim, with no `content-to-image` call. |

The mission slide is the one perspective that never drops: absent docs surface
as the reflection-questions slide, not a missing slide. This is the
not-defined-so-ask pattern shared with `dev-analysis-mission`.

## Selecting from a release context

`collect-diff.sh` always produces `diff-facts.json`. The other fact sources
(`dev-analysis-architecture`, `-security`, `-dependencies`, `-quality`,
`dev-test-contracts`, `dev-analysis-mission`) are external fragments produced
by their own Skills; this Skill does not run them. When run standalone the
applicable set is whichever fragments the caller staged plus the always-on
perspectives backed by `diff-facts.json` (architecture impact, API & contract
surface, data & schema changes). When run inside a framework report the full
staged fragment set is available and every perspective whose source is present
is included.

## Out of scope

Running the `dev-analysis-*` engines (their own Skills do; this Skill consumes
their fragments and `collect-diff.sh` output). Inventing a perspective with no
static fact source — see [`perspective-discovery.md`](perspective-discovery.md).
Writing the narrative or the image brief — see
[`perspective-synthesis.md`](perspective-synthesis.md).
