# Dev-tooling Catalog

The open-source tools that back the `dev-analysis-`/`dev-test-`/`dev-report-`
Skills, what question each answers, and where each is owned. Placement follows
the [taxonomy](dev-skill-taxonomy.md); fragments conform to the
[report contract](dev-report-framework.md).

## Contents

- [Constraints](#constraints)
- [Runtime policy](#runtime-policy)
- [Catalog](#catalog)
- [Excluded commercial tools and their replacements](#excluded-commercial-tools-and-their-replacements)
- [CodeQL — optional, licensing-gated](#codeql--optional-licensing-gated)
- [F# architecture limitation](#f-architecture-limitation)
- [Product mission analysis](#product-mission-analysis)

## Constraints

Only open-source, free, self-hostable tools. Commercial tools requested in the
brief (NDepend, SemanticDiff) are replaced with OSS equivalents; CodeQL is kept
optional because its license is free only for public repositories. Stacks in
scope: .NET/C#, F#, TypeScript/JavaScript, Python, Rust, GraphQL.

## Runtime policy

Three runtimes are assumed available: `bash`/`python3`, Node, Docker. No host
JRE — the JVM tools (code-maat, OWASP Dependency-Check, Structurizr) run via
their official Docker images.

A runner script never installs anything. It detects its tool and, if missing,
prints the exact install command **and** the pinned `docker run` line, then
exits `3`. This is the "scripts solve, don't punt" rule applied to missing
tools.

## Catalog

Every tool from the brief appears exactly once, grouped by its owning Skill.
"Runtime" is what the runner needs present.

### dev-analysis-architecture — does structure match intent?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| Structurizr (Lite/CLI) | any (DSL), .NET (from-code) | Docker | Apache-2.0 | C4 model + diagrams; official `structurizr/lite` and `structurizr/cli` images. |
| dependency-cruiser | TS/JS | Node | MIT | Module-boundary rules + dependency graph. |
| Nx Graph | TS/JS (Nx workspaces) | Node | MIT | `nx graph --file` project graph for Nx monorepos. |
| madge | TS/JS | Node | MIT | Circular-dependency detection independent of a dependency-cruiser config. |
| MSADoc | .NET | dotnet | MIT | Per-service metadata → service catalog / API-flow diagrams. |
| ArchUnitNET / NetArchTest | .NET/C# (F# limited) | dotnet | Apache-2.0 / MIT | Layering and dependency rules as test assertions. OSS replacement for NDepend. |
| cargo-modules | Rust | cargo | MIT/Apache-2.0 | Rust module/dependency graph. |

### dev-analysis-evolution — how has the codebase changed?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| git-of-theseus | any | python3 (pip; detect-not-install) | MIT | Code survival/age cohorts across history. |
| code-maat | any | Docker | GPL-3.0 | Temporal coupling, churn, authorship; official image, no host Java. |
| `git diff --dirstat=files,0`, `--numstat`, per-file-type, per-author | any | bash + python3 | GPL-2.0 (git) / stdlib | Per-directory/extension/author change distribution across multiple release tags. |
| per-author PR activity classification | any | bash + python3 + role | GPL-2.0 (git) / stdlib | Per author: PR count, each PR typed (New feature / Updated feature / Bug / Technical / Configuration / Data), feature PRs split New-patterns vs Existing-patterns, and a "vibe coder" flag **only if the repo defines the term**. Static collector + classification role. |

### dev-analysis-dependencies — what do we depend on, is it safe?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| OWASP Dependency-Check | .NET, F#, TS/JS, Py | Docker | Apache-2.0 | CVE scan of declared dependencies; official image. |
| Trivy | all | Docker | Apache-2.0 | SCA + SBOM + license + config scan, multi-ecosystem. |
| Syft + Grype | all | Docker | Apache-2.0 | Formal SBOM generation (Syft) + vulnerability match (Grype). |
| cargo-audit | Rust | cargo | MIT/Apache-2.0 | RustSec advisory-DB scan. |
| cargo-geiger | Rust | cargo | Apache-2.0/MIT | `unsafe`-code surface including dependencies. |

### dev-analysis-quality — is the code sound and within policy?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| Semgrep CE | all | Docker | LGPL-2.1 | SAST + custom rules. Portable default. Runner owned here, shared with `dev-analysis-security`. |
| Open Policy Agent + Conftest | config/IaC/JSON (stack-agnostic) | Docker / bash | Apache-2.0 | Policy-as-code over manifests, IaC, structured config. |
| scc / tokei | all | bash | MIT / MIT-Apache-2.0 | LOC, complexity, and cost metrics; cheap stable `metrics{}`. |
| difftastic | all (incl. Rust) | bash | MIT | Structural multi-language diff. OSS replacement for SemanticDiff. |
| static code-diff summarizer | all | role over difftastic | — | A `references/` role; turns difftastic structural output into prose. No external binary. |
| CodeQL | C#, TS/JS, Py | Docker | proprietary (see below) | Optional, licensing-gated. Never depended on. |

### dev-analysis-security — what is the attack surface?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| Semgrep (taint/network rulesets) | TS/JS, Py, C# (Rust/F# thinner) | Docker | LGPL-2.1 | Calls the runner owned by `dev-analysis-quality` with security rulesets. |
| network & data-flow analysis | all | bash + python3 / Docker | stdlib + Semgrep | Static egress/ingress inventory + taint paths. Data-flow is folded into this Skill, not a separate one. |
| gitleaks | any | Docker | MIT | Committed-secret scan. |
| trufflehog | any | detect-not-install | AGPL-3.0 | Verified-secret detection (validates credentials live); deeper second pass. |

### dev-analysis-schema — did the contracts change?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| oasdiff | OpenAPI emitters (TS/JS, Py, .NET) | Docker | Apache-2.0 | OpenAPI structural + breaking-change diff; run separately for public and private. |
| graphql-inspector | GraphQL | Node | MIT | Schema diff classified breaking / dangerous / safe. |
| MCP JSON-Schema differ | MCP servers | python3 (stdlib) | — | A stdlib structural JSON-Schema diff. No external engine. No DB schema diff is in scope. |

### dev-test-contracts — do providers honor consumer contracts?

| Tool | Stacks | Runtime | License | Notes |
| ---- | ------ | ------- | ------- | ----- |
| pact.io | TS/JS, .NET, Py, Rust, GraphQL | per-stack + Docker (optional broker) | MIT | Consumer/provider contract verification; executes the provider. |

### dev-report — assembly and presentation

| Capability | Owning Skill | Runtime | Notes |
| ---------- | ------------ | ------- | ----- |
| Fragment validation + report build + standalone "Release candidate report" | `dev-report-framework` | python3 (stdlib) + CDN libs | Owns the contract (`view` two-column release/Δ tag, `files[]` preview, table `children`, `image`, `d3-graph` force/dag/chord). Per-section top menu, show/hide previous releases, a global `Module:` filter (ids resolved by the shared `scripts/modules.py` from `dev-process.json` `modules`), optional DESIGN.md theming. CDN: marked/DOMPurify/D3 v7/Mermaid. |
| Multi-perspective `git diff` → Slidev deck | `dev-report-release-diff` | bash + python3, Node (Slidev, MIT) | Reuses evolution's diff collectors, `dev-analysis-schema`, and `content-to-image` (one image per perspective). |
| Pinned report landing page (scope infographic + bullets) | `dev-report-overview` | python3 (stdlib), reuses `content-to-image` | Runs last; reads the assembled fragments + scope; emits the `overview` fragment the framework pins as the default landing. |
| Unit test coverage / e2e test reports | none — **empty slots** | n/a | Categories `test-coverage` and `test-reports` exist in the contract + nav; the consuming repo wires its own tool via a `dev-process.json` `analysis`/`review` entry. No producer ships. |

The `git diff main...feature` multi-perspective capability from the brief is
`dev-report-release-diff`. The eight default perspectives are: architecture
impact, API & contract surface, data & schema changes, security & attack
surface, dependency & supply-chain, test coverage & risk, performance &
resource, operational & observability. Repo-specific perspectives are admitted
only when a static fact source for them exists.

## Excluded commercial tools and their replacements

| Requested (commercial) | Replacement (OSS) | Owning Skill |
| ---------------------- | ----------------- | ------------ |
| NDepend (.NET architecture rules) | ArchUnitNET / NetArchTest | `dev-analysis-architecture` |
| SemanticDiff (structural diff) | difftastic | `dev-analysis-quality` |

## CodeQL — optional, licensing-gated

The CodeQL CLI is free to run on **public/open-source** repositories and for
academic research. On private or proprietary code, automated analysis requires
GitHub Advanced Security (paid). Therefore Semgrep CE is the portable default
for `dev-analysis-quality`, and **no pipeline depends on CodeQL**. A
`references/codeql-optional.md` enables it where the license permits; it is
never required for a fragment to be produced.

## F# architecture limitation

ArchUnitNET and NetArchTest reflect over compiled CLR assemblies. This maps
cleanly to C# types and namespaces but poorly to idiomatic F# modules and
functions, so F# layering rules are weak. F# architecture analysis falls back
to a hand-authored Structurizr DSL model rather than reflection-based rules.
This limitation is stated wherever F# is in scope.

## Product mission analysis

`dev-analysis-mission` answers whether a change serves the product's stated
mission. A stdlib script inventories product-intent docs
(`MISSION.md`, `VISION.md`, `docs/product*`, `docs/strategy*`,
`docs/roadmap*`, OKR/PRD files) and the change set; a `references/` role maps
each significant change to the mission goal it serves and flags scope creep.

When no (or only thin) mission documentation exists, the fragment is
`status: info` and its body is the set of reflection questions to answer
instead — what the product's purpose is, who it is for, what outcome it drives,
what is explicitly out of scope, how mission progress is measured, and whether
the change serves a stated goal or is speculative. This makes the gap
actionable rather than silently absent, and it is the static signal that lets
`dev-report-release-diff` add a conditional "mission alignment" perspective.
