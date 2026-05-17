# Skills

Each subdirectory is one self-contained Skill: a `SKILL.md` plus its
`references/` and `scripts/`. The agent loads each Skill's `name` +
`description` at startup and reads the rest only when a request matches.

## Available Skills

| Skill | Description |
| --- | --- |
| [content-to-image](content-to-image/SKILL.md) | Convert a piece of text into a single explanatory illustration via a 3-step pipeline (extract → art-direct → prompt-synth), then render with gpt-image (Azure Foundry or the OpenAI API). |
| [dev-release-candidate](dev-release-candidate/SKILL.md) | Build a release candidate driven by dev-process.json: branch from origin/main, compute the main↔production scope, run configured analysis/review tools in parallel (heavy ones as sub-agents), optionally generate changelog/notes and an aggregated viewer, and make the release-candidate commit. Informs about the freeze/notify/push steps it does not perform. |
| [dev-release-publish](dev-release-publish/SKILL.md) | Finalize a verified release candidate: rewrite the release-candidate commit so report artifacts go to AWS S3 / Azure Blob instead of git history while configured reports stay committed. Informs about the approval/production-release/notify steps it does not perform. |
| [dev-report-framework](dev-report-framework/SKILL.md) | Aggregate report fragments into one standalone HTML "Release candidate report" per release: every fragment in a two-column This-release / Δ-vs-previous layout, per-section top menu, in-place file/markdown preview, show/hide previous releases, optional DESIGN.md theming. Owns the fragment JSON contract (`view` tag, `files[]`, table `children`, `image`, `d3-graph` force/dag/chord), `validate_fragments.py`, and `dev-report-build`. |
| [dev-analysis-evolution](dev-analysis-evolution/SKILL.md) | Analyze git history across releases — code survival (git-of-theseus), churn/coupling/authorship (code-maat via Docker), an expandable extension → folder → file change drill-down, and per-author PR activity classification (module-filterable, optional "vibe coder" label). Emits `evolution` and `author-activity` fragments. |
| [dev-analysis-schema](dev-analysis-schema/SKILL.md) | Structurally diff API/data contracts between two refs — OpenAPI (oasdiff), GraphQL (graphql-inspector), MCP (stdlib JSON-Schema), split public vs private; the LLM summary runs only when a diff exists. Public breaking change ⇒ status error. |
| [dev-analysis-architecture](dev-analysis-architecture/SKILL.md) | Extract structure and check it against intent — dependency-cruiser, Nx Graph, madge, Structurizr, MSADoc, ArchUnitNET/NetArchTest, cargo-modules, with a tool-free fallback (stdlib import scan → dependency graph + import-flow Sankey + C4 mermaid + ADR index) when no analyzer is installed. Emits an `architecture` fragment. |
| [dev-analysis-dependencies](dev-analysis-dependencies/SKILL.md) | Scan third-party dependencies and supply chain — OWASP Dependency-Check, Trivy, Syft+Grype, cargo-audit/cargo-geiger — deduped across scanners and grouped per library (each library expands to its CVEs). Any critical vulnerability ⇒ status error. |
| [dev-analysis-quality](dev-analysis-quality/SKILL.md) | Static code-quality and policy — Semgrep CE (the shared repo-root runner), OPA/Conftest, scc, difftastic-based code-diff summary, optional CodeQL. Emits a `quality` fragment. |
| [dev-analysis-security](dev-analysis-security/SKILL.md) | Attack-surface analysis — static network egress/ingress inventory, Semgrep taint/security rulesets (shared runner), gitleaks, optional trufflehog. Data-flow folded in here. Any verified secret ⇒ status error. |
| [dev-analysis-mission](dev-analysis-mission/SKILL.md) | Assess whether a change serves the product's stated mission by inventorying vision/mission/strategy docs and the change set; when no mission docs exist, emits the reflection questions to answer instead. |
| [dev-test-contracts](dev-test-contracts/SKILL.md) | Execute consumer/provider contract verification (pact.io, per-stack verifier); the `contracts` fragment status is the pass/fail verdict and any failed interaction blocks. |
| [dev-report-release-diff](dev-report-release-diff/SKILL.md) | Turn a `git diff` ref-range into a multi-perspective Slidev deck: collect static diff facts (reusing the shared collectors + schema diff), synthesize 8 curated perspectives, and render one content-to-image illustration per perspective. |
| [dev-report-overview](dev-report-overview/SKILL.md) | Runs last: reads the assembled fragment set + scope, invokes content-to-image for a scope infographic, and emits the pinned `overview` fragment (infographic + high-level bullets) the framework shows as the report's default landing page. |

## Adding a Skill

See [docs/repository-structure.md](../docs/repository-structure.md#adding-a-new-skill)
and the checklist in [docs/authoring-skills.md](../docs/authoring-skills.md#checklist).
Add a row to the table above when you do.

A Skill is self-contained: roles it delegates to live in its own
`references/`, never as a globally-registered private subagent. See
[docs/skills-vs-agents.md](../docs/skills-vs-agents.md).
