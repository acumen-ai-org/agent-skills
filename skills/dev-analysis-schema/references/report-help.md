# Reading the schema-diff fragment

This part answers one question: what does this release change in the API and
schema contract, and does the break hit the public or only the private
surface? The diff is the production..main delta — every section here describes
what changes versus production, so it reads in the production column.

## Summary cards

Four counts: whether there is any diff, public breaking changes, private
breaking changes, and total changes across the OpenAPI, GraphQL, and MCP
surfaces.

What to look for: `Public breaking` above zero. Any public breaking change is
`status: error` — a consumer-visible contract break. `Private breaking` only
is `status: warn`; non-breaking change is also `warn`; no diff is `ok`.

What it means: the cards are the `hasDiff` / `publicBreaking` /
`privateBreaking` / `totalChanges` metrics, diffed release-over-release.

## Schema changes

Every change, one row each: surface (OpenAPI / GraphQL / MCP), visibility
(public / private), criticality (BREAKING / DANGEROUS / SAFE), location, and
detail.

What to look for: rows where visibility is `public` and criticality is
`BREAKING` — those drive the error status. Filter by surface to isolate which
contract moved.

## Tooling note

Present only when a diff engine was unavailable (Docker/Node missing).
Coverage is partial.

What to look for: if present, the diff is incomplete — re-run with the engine
installed before trusting a "no public breaking change" conclusion.

## Assessment (role-written)

When there is a diff, the `schema-diff-summary` role adds a narrative: what
broke or was added, for whom, the single highest-risk item by name, and
whether consumer action is required.
