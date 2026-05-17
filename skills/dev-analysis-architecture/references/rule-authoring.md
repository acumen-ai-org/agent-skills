# Authoring a layering rule per stack

How to express the same architectural intent — "a lower layer must not depend
on an upper layer; module boundaries are not crossed" — in each stack's
analyzer, so `to-fragment.py` sees a violation it can map to `status`. This is
read when you set up the rules for a repo, not on every run.

## Contents

- [The shape of a layering rule](#the-shape-of-a-layering-rule)
- [TypeScript / JavaScript — dependency-cruiser](#typescript--javascript--dependency-cruiser)
- [TypeScript / JavaScript — madge and Nx](#typescript--javascript--madge-and-nx)
- [.NET / C# — ArchUnitNET / NetArchTest](#net--c--archunitnet--netarchtest)
- [.NET services — MSADoc](#net-services--msadoc)
- [Rust — cargo-modules](#rust--cargo-modules)
- [Any stack — Structurizr DSL](#any-stack--structurizr-dsl)
- [F# architecture limitation](#f-architecture-limitation)
- [Severity and how it reaches the fragment](#severity-and-how-it-reaches-the-fragment)
- [Out of scope](#out-of-scope)

## The shape of a layering rule

A layering rule has three parts: the **layers** (an ordered list of path or
namespace globs), the **allowed direction** (upper may depend on lower, never
the reverse), and a **severity** (`error` for a true breach, `warn` for an
advisory finding). Every analyzer below expresses these three; only the syntax
differs. Keep the layer globs identical across analyzers for one repo so a
multi-stack repo reports comparably.

## TypeScript / JavaScript — dependency-cruiser

`.dependency-cruiser.js` `forbidden` rules. A lower layer importing an upper
one is the canonical breach:

```js
module.exports = {
  forbidden: [
    {
      name: "no-domain-to-ui",
      severity: "error",
      from: { path: "^src/domain" },
      to:   { path: "^src/ui" },
    },
    {
      name: "no-circular",
      severity: "warn",
      from: {},
      to: { circular: true },
    },
  ],
};
```

`run-depcruise.sh` defaults to `--no-config` (graph only). Point it at a repo
config by adding `--config .dependency-cruiser.js` to the runner invocation
line; `summary.violations[]` then carries `rule.name` and `rule.severity`,
which `to-fragment.py` reads verbatim.

## TypeScript / JavaScript — madge and Nx

madge has no rule language — it answers exactly one question, "are there import
cycles", and `run-madge.sh` runs `--circular`. Every returned chain becomes a
cycle in the fragment (`status: warn`). Use it as the boundary-independent
cycle check next to dependency-cruiser's configured rules.

Nx enforces boundaries through `@nx/enforce-module-boundaries` ESLint tags in
`nx.json`/project config; `run-nx-graph.sh` captures the resulting project
graph, and cycles in that graph surface the same way. Tag-violation reporting
lives in the lint run, not the graph export — keep the cycle signal here and
the tag rules in the repo's lint gate.

## .NET / C# — ArchUnitNET / NetArchTest

Layering rules are xUnit/NUnit test assertions in a dedicated arch-test
project. ArchUnitNET:

```csharp
[Fact]
public void Domain_must_not_depend_on_Ui()
{
    Types().That().ResideInNamespace("App.Domain")
        .Should().NotDependOnAny(
            Types().That().ResideInNamespace("App.Ui"))
        .Check(Architecture);
}
```

NetArchTest equivalent:

```csharp
var result = Types.InAssembly(typeof(DomainMarker).Assembly)
    .That().ResideInNamespace("App.Domain")
    .ShouldNot().HaveDependencyOn("App.Ui")
    .GetResult();
Assert.True(result.IsSuccessful);
```

`run-archunitnet.sh` runs `dotnet test` with a TRX logger; a failed assertion
becomes a `failed` result that `to-fragment.py` maps to an `error`-severity
violation (exit 4). Name each test after the rule — the test name is the rule
name in the fragment.

## .NET services — MSADoc

MSADoc is descriptive, not assertive: it extracts a per-service catalog with
declared inter-service dependencies. `run-msadoc.sh` turns that into the
service graph; an unexpected service→service edge shows as a graph edge, and a
cycle among services becomes a fragment cycle. Encode "service A must not call
service B" as an ArchUnitNET rule on the calling project, not in MSADoc.

## Rust — cargo-modules

cargo-modules emits the module/dependency graph; it does not assert rules.
`run-cargo-modules.sh` captures `cargo modules dependencies`; module cycles
become fragment cycles (`status: warn`). For a hard layering rule in Rust,
keep the boundary visible through the crate's module privacy
(`pub(crate)` / `pub(in path)`) and assert direction in a unit test that
imports across the boundary and fails to compile if the boundary is wrong; the
graph here is the detection signal, the type system is the enforcement.

## Any stack — Structurizr DSL

When no reflection/graph analyzer fits (or to model intended architecture
independently of code), hand-author a Structurizr DSL workspace. The DSL is
the source of truth for *intended* structure; `run-structurizr.sh` exports it
to JSON and `to-fragment.py` renders the C4 model as the graph. A relationship
absent from the DSL but present in code is the gap to report — compare the DSL
graph fragment against the code-derived graph fragment.

## F# architecture limitation

ArchUnitNET and NetArchTest reflect over compiled CLR assemblies. This maps
cleanly to C# types and namespaces but poorly to idiomatic F# modules and
functions (F# compiles modules to static classes and functions to methods, so
namespace/type assertions do not express F# module boundaries). **F# layering
rules are therefore weak and must not be relied on.**

For F# components, do not write reflection rules. Model the intended
architecture as a hand-authored Structurizr DSL workspace and run
`run-structurizr.sh`; the DSL is the architectural contract for F# code, and
the exported graph is what the fragment carries. State this limitation in any
report covering an F# codebase so the absence of reflection-based rules is
explained, not silently missing.

## Severity and how it reaches the fragment

`to-fragment.py` maps a violation whose severity is `error`/`blocking` to
`status: error` and exit `4`; cycles and any other violation to `status:
warn`; a clean graph to `status: ok`. So: mark a real layering breach
`error` in the analyzer's rule definition, leave advisory checks at `warn`,
and let cycles fall through as `warn` automatically. The synthesis role may
raise `warn` to `error` for a named breach but never lowers it.

## Out of scope

Running the analyzers (the runner scripts do that). Interpreting the resulting
graph into prose (`architecture-synthesis.md` does that). The fragment JSON
shape (the framework's `fragment-schema.md` owns it).
