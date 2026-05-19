# Visibility rules: public vs private API surface

`classify-endpoints.py` splits an OpenAPI document into a public and a private
sub-document so a breaking change can be scored by audience. The same
public/private distinction governs GraphQL and MCP. A breaking change on the
**public** surface is `status: error`; private-only breaking is `status: warn`.
The signals below are the defaults; every one is overridable by environment
variable so a repo with different conventions is not misclassified.

## Signals (first match wins, in this order)

1. **Public allowlist** — a path matching `SCHEMA_PUBLIC_PATH_PATTERNS`
   (comma-separated regexes, default empty) is public unless it also carries an
   internal-extension flag. Use this when most of the surface is internal and
   only a named set is published.
2. **Internal extension** — an OpenAPI operation or whole path object carrying
   the vendor extension named by `SCHEMA_INTERNAL_EXTENSION` (default
   `x-internal`) set to `true` is private. A path-level flag makes every
   operation under it private.
3. **Private path pattern** — a path matching any regex in
   `SCHEMA_PRIVATE_PATH_PATTERNS` (default `^/internal`, `^/admin`, `^/_`,
   `^/debug`, `/internal/`) is private.
4. **Private security scheme** — an operation whose effective `security` (its
   own, else the document default) names a scheme listed in
   `SCHEMA_PRIVATE_SECURITY_SCHEMES` (comma-separated, default empty) is
   private. Use this when an internal mTLS / service-token scheme marks the
   non-public surface.
5. **Default** — anything unmatched is public. A surface is private only when a
   signal says so; absence of a signal never implies private.

## GraphQL

GraphQL SDL has no path. A type or field is treated as private when it carries
an `@internal` directive (override the directive name with
`SCHEMA_GRAPHQL_INTERNAL_DIRECTIVE`) or its name is absent from a configured
allowlist file pointed at by `SCHEMA_GRAPHQL_PUBLIC_ALLOWLIST` (one name per
line). With neither configured, the whole GraphQL surface is public and any
breaking GraphQL change is scored as public.

## MCP

MCP tool/resource JSON-Schemas have no visibility convention in the protocol;
they are public by default. To mark a tool private, list its
`tools:<name>` / `resources:<name>` identifier (one per line) in the file
pointed at by `SCHEMA_MCP_PRIVATE_ALLOWLIST`.

## Overriding

All knobs are environment variables read by `classify-endpoints.py`:

| Variable | Default | Effect |
| -------- | ------- | ------ |
| `SCHEMA_PUBLIC_PATH_PATTERNS` | (empty) | Comma-separated regexes forced public. |
| `SCHEMA_INTERNAL_EXTENSION` | `x-internal` | Vendor extension key meaning private. |
| `SCHEMA_PRIVATE_PATH_PATTERNS` | `^/internal,^/admin,^/_,^/debug,/internal/` | Comma-separated regexes meaning private. |
| `SCHEMA_PRIVATE_SECURITY_SCHEMES` | (empty) | Security-scheme names meaning private. |
| `SCHEMA_GRAPHQL_INTERNAL_DIRECTIVE` | `@internal` | GraphQL directive meaning private. |
| `SCHEMA_GRAPHQL_PUBLIC_ALLOWLIST` | (unset) | File of public GraphQL names. |
| `SCHEMA_MCP_PRIVATE_ALLOWLIST` | (unset) | File of private MCP tool/resource ids. |

Set them in the calling environment before `diff-schemas.sh` runs; the split
is recomputed at both refs so a visibility change is itself observable.

## Out of scope

Deciding whether a change is breaking (that is the diff engines'
classification, refined by `schema-diff-summary.md`). DB schema visibility
(this Skill does not diff databases). Authentication design review (security is
`dev-analysis-security`).
