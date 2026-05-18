# Reading the architecture report

What each section means and how to read it.

## Summary and metric cards

The lead group. **Modules** is the node count, **Dependencies** the edge
count, **Cycles** the number of strongly-connected components larger than one
node, **Max depth** the longest acyclic dependency path. These four numbers
diff release-to-release: a rising cycle count or depth is structural drift.

## Dependency graph

A node-link graph of the module dependencies. Boxes are modules (when the
repo defines a module set) or files/packages; arrows point from importer to
imported. Cycle members render in their own group so feedback loops stand
out. A `dag` layout means the graph is layered; `force` means organic;
`chord` means coupling is effectively all-to-all. Look for a module that
everything points at (a hub — high change risk) and for arrows that go
"backwards" against the intended layering.

## Cycles

Each row is one dependency cycle: the member chain and its length. A cycle
means no member can be built, tested, or replaced in isolation. The shortest
cycle through the most-depended-on modules is the highest unwind risk —
break one edge in it to remove the whole cycle.

## Rule violations

Each row is one boundary or layering rule the analyzer flagged: the rule, its
severity, and the offending `from -> to` edge. An `error`/`blocking` severity
is a hard layering breach (a lower layer importing an upper one, or a
forbidden cross-module edge) and fails the release gate. A `warn` is advisory
(a naming or visibility nit) - review it, but it does not block.

## Flow

A sankey of import volume between modules (or packages), weighted by the
number of import statements. Wide bands are heavy coupling; a band into a
module from many sources marks a shared dependency whose change ripples
widely.

## C4 context / container

A module-level container diagram: each box is a resolved module, each arrow
an inter-module import. It appears only when the repo resolves to two or more
modules with at least one inter-module edge. Read it as the intended shape of
the system - compare it against the dependency graph to spot edges that
should not exist.
