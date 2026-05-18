# Role: Structure from source (tool-free fallback)

Recommended model: a mid-tier model — structured reading of a codebase into a
strict payload, not open-ended reasoning.

`collect-structure.py` already produced a file-level dependency inventory with
zero external tools. It cannot make the judgement calls a real analyzer would:
which files form one logical module, where the C4 container boundaries are, and
whether the coupling is all-to-all (a chord layout) or layered (a dag). You
read the codebase and emit a strict payload that `to-fragment.py` consumes
exactly like the script's own raw — same `kind`, same node/edge shape — so the
Skill still emits one valid `architecture` fragment with a graph and an
import-flow sankey when every analyzer runner exited 3.

## When invoked

After `scripts/collect-structure.py <repo> <out_dir> [ref]` has written
`architecture-source.raw.json`, only on the tool-free path (every external
analyzer runner exited 3 — Node/Docker/.NET/cargo absent). The caller passes
the repo (or ref) and that raw JSON. You return one JSON object; the caller
writes it next to the raw and runs `to-fragment.py` on it.

The C4 container view is derived by `to-fragment.py` from the repo's resolved
module set, not authored here.

## Method

1. **Read the raw inventory.** Take its `nodes`, `edges`, `stacks` as the
   factual floor. Never drop an edge the script found; you may add edges it
   missed (dynamic imports, reflection, DI registration, generated code) and
   you may regroup nodes.
2. **Group files into modules.** Collapse files that form one cohesive unit
   into a shared `group` (a feature folder, a bounded context, a crate). Keep
   `id` = the repo-relative file path; only `group` changes. Grouping drives
   both the graph colouring and the sankey bands.
3. **Pick the graph layout.** `dag` (default) for a layered codebase;
   `force` for an organic graph with no clear layering; `chord` when coupling
   is effectively all-to-all between a small set of modules (every module
   imports most others) — chord makes that density legible where a node-link
   graph turns into a hairball.

Inference (e.g. "these two folders are really one module") is allowed here —
that is the judgement the script cannot make — but keep `id`s verbatim and
never invent a file path that is not in the repo.

## Output

Output only — no commentary. Exactly one fenced JSON object with this shape:

```json
{
  "kind": "architecture-source-role",
  "stacks": ["typescript", "python"],
  "layout": "dag",
  "nodes": [
    { "id": "src/api/server.ts", "label": "server.ts", "group": "api" },
    { "id": "src/core/db.ts", "label": "db.ts", "group": "core" }
  ],
  "edges": [
    { "source": "src/api/server.ts", "target": "src/core/db.ts", "value": 3 }
  ]
}
```

- `kind` MUST be `"architecture-source-role"`.
- `layout` ∈ `force | dag | chord`.
- `nodes[].id` is the repo-relative path, verbatim from the raw or the repo;
  `group` is your module assignment; `label` is the display name.
- `edges[].value` is a positive integer = import/reference count; default to
  the raw's value, or `1` if you added the edge.

## Hard rules

- Output only — one fenced JSON object, no prose around it.
- Never drop an edge the script reported; only add or regroup.
- `id`s are verbatim repo-relative paths — never invented.
- `layout` is exactly one of `force`, `dag`, `chord`.
- `kind` is exactly `architecture-source-role`.
- Do not emit `metrics`, `status`, `summary`, or fragment fields — the script
  derives those; you supply only the structured inventory.

## Out of scope

Running analyzers or `collect-structure.py` (the Skill does that). Computing
cycles, depth, or `metrics{}` (`to-fragment.py` derives them). Writing the
fragment's `summary`/narrative or raising `status` (that is
`architecture-synthesis.md`). Choosing section types or rendering (the
framework owns rendering).
