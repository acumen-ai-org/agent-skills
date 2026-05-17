#!/usr/bin/env python3
"""Normalize an architecture tool's raw output into one dev-report fragment.

Usage: to-fragment.py <id> <raw_file> <out_fragment_json>

Emits exactly one fragment, category "architecture", schema
dev-report-fragment/v1. The raw file is auto-detected among the formats the
runner scripts produce:

  - dependency-cruiser  --output-type json
  - madge               --json  (adjacency map) and --circular --json
  - nx graph            --file  (graph.json)
  - cargo-modules       --acyclic off, dot output
  - Structurizr CLI     workspace export / inspection json
  - MSADoc              service catalog json
  - ArchUnitNET / NetArchTest  trx / json test result

The graph becomes a d3-graph body; metrics carry node_count, edge_count,
cycle_count, max_depth; any reported violation drives status (warn for
cycles/soft rule findings, error for hard layering violations) and exit 4.

Exit codes:
  0  fragment written; status ok or warn
  1  bad arguments
  2  raw output unparseable; nothing written
  4  fragment written with status error (blocking violations)
"""
import datetime
import json
import pathlib
import re
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"
SKILL_NAME = "dev-analysis-architecture"
GRAPH_NODE_RENDER_LIMIT = 300


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tarjan_scc(adjacency):
    index_counter = [0]
    stack = []
    on_stack = set()
    indices = {}
    low_links = {}
    components = []

    def strongconnect(node):
        work = [(node, 0)]
        while work:
            current, child_index = work[-1]
            if child_index == 0:
                indices[current] = index_counter[0]
                low_links[current] = index_counter[0]
                index_counter[0] += 1
                stack.append(current)
                on_stack.add(current)
            recursed = False
            successors = adjacency.get(current, ())
            while child_index < len(successors):
                successor = successors[child_index]
                if successor not in indices:
                    work[-1] = (current, child_index + 1)
                    work.append((successor, 0))
                    recursed = True
                    break
                if successor in on_stack:
                    low_links[current] = min(low_links[current], indices[successor])
                child_index += 1
            if recursed:
                continue
            if low_links[current] == indices[current]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == current:
                        break
                components.append(component)
            work.pop()
            if work:
                parent = work[-1][0]
                low_links[parent] = min(low_links[parent], low_links[current])

    for vertex in list(adjacency.keys()):
        if vertex not in indices:
            strongconnect(vertex)
    return components


def cycles_from_components(components):
    return [sorted(component) for component in components if len(component) > 1]


def longest_path_in_dag(adjacency, cycle_members):
    memo = {}
    visiting = set()

    def depth(node):
        if node in cycle_members:
            return 0
        if node in memo:
            return memo[node]
        if node in visiting:
            return 0
        visiting.add(node)
        best = 0
        for successor in adjacency.get(node, ()):
            if successor in cycle_members:
                continue
            best = max(best, 1 + depth(successor))
        visiting.discard(node)
        memo[node] = best
        return best

    overall = 0
    for vertex in adjacency:
        overall = max(overall, depth(vertex))
    return overall


def build_metrics(nodes, edges, cycles, adjacency):
    cycle_members = set()
    for cycle in cycles:
        cycle_members.update(cycle)
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "cycle_count": len(cycles),
        "max_depth": longest_path_in_dag(adjacency, cycle_members),
    }


def adjacency_from_edges(node_ids, edges):
    adjacency = {node_id: [] for node_id in node_ids}
    for source, target in edges:
        adjacency.setdefault(source, [])
        adjacency.setdefault(target, [])
        adjacency[source].append(target)
    return adjacency


def parse_depcruise(raw):
    modules = raw.get("modules")
    if not isinstance(modules, list):
        return None
    node_ids = []
    edges = []
    seen = set()
    for module in modules:
        source = module.get("source")
        if not isinstance(source, str):
            continue
        if source not in seen:
            seen.add(source)
            node_ids.append(source)
        for dependency in module.get("dependencies", []):
            resolved = dependency.get("resolved")
            if not isinstance(resolved, str):
                continue
            edges.append((source, resolved))
    for _, target in edges:
        if target not in seen:
            seen.add(target)
            node_ids.append(target)
    violations = []
    summary = raw.get("summary", {})
    for violation in summary.get("violations", []) if isinstance(summary, dict) else []:
        rule = violation.get("rule", {})
        rule_name = rule.get("name", "rule")
        severity = rule.get("severity") or violation.get("rule", {}).get("severity", "warn")
        violations.append(
            {
                "rule": rule_name,
                "severity": severity,
                "from": violation.get("from", ""),
                "to": violation.get("to", ""),
            }
        )
    return node_ids, edges, violations, "dependency-cruiser"


def parse_madge(raw):
    if not isinstance(raw, dict):
        return None
    if "circular" in raw and isinstance(raw["circular"], list) and "graph" not in raw:
        circular = raw["circular"]
        node_ids = []
        edges = []
        seen = set()
        for chain in circular:
            previous = None
            for member in chain:
                if member not in seen:
                    seen.add(member)
                    node_ids.append(member)
                if previous is not None:
                    edges.append((previous, member))
                previous = member
            if chain and len(chain) > 1:
                edges.append((chain[-1], chain[0]))
        return node_ids, edges, [], "madge"
    if all(isinstance(value, list) for value in raw.values()) and raw:
        node_ids = []
        edges = []
        seen = set()
        for source, targets in raw.items():
            if source not in seen:
                seen.add(source)
                node_ids.append(source)
            for target in targets:
                edges.append((source, target))
        for _, target in edges:
            if target not in seen:
                seen.add(target)
                node_ids.append(target)
        return node_ids, edges, [], "madge"
    return None


def parse_nx_graph(raw):
    graph = raw.get("graph") if isinstance(raw, dict) else None
    if not isinstance(graph, dict):
        return None
    project_nodes = graph.get("nodes")
    dependencies = graph.get("dependencies")
    if not isinstance(project_nodes, dict) or not isinstance(dependencies, dict):
        return None
    node_ids = list(project_nodes.keys())
    edges = []
    for source, deps in dependencies.items():
        for dependency in deps:
            target = dependency.get("target")
            if isinstance(target, str):
                edges.append((source, target))
    return node_ids, edges, [], "nx"


def parse_dot(text):
    edge_pattern = re.compile(r'"([^"]+)"\s*->\s*"([^"]+)"')
    node_pattern = re.compile(r'^\s*"([^"]+)"\s*\[')
    node_ids = []
    edges = []
    seen = set()
    for match in node_pattern.finditer(text):
        identifier = match.group(1)
        if identifier not in seen:
            seen.add(identifier)
            node_ids.append(identifier)
    for match in edge_pattern.finditer(text):
        source, target = match.group(1), match.group(2)
        for identifier in (source, target):
            if identifier not in seen:
                seen.add(identifier)
                node_ids.append(identifier)
        edges.append((source, target))
    if not node_ids and not edges:
        return None
    return node_ids, edges, [], "cargo-modules"


def parse_structurizr(raw):
    model = raw.get("model") if isinstance(raw, dict) else None
    if not isinstance(model, dict):
        return None
    elements = []
    for collection_key in ("softwareSystems", "people", "deploymentNodes"):
        elements.extend(model.get(collection_key, []) or [])
    node_ids = []
    edges = []
    seen = set()

    def register(element):
        identifier = element.get("id") or element.get("name")
        if identifier and identifier not in seen:
            seen.add(identifier)
            node_ids.append(str(identifier))
        for container in element.get("containers", []) or []:
            register(container)
            for component in container.get("components", []) or []:
                register(component)

    for element in elements:
        register(element)
    for relationship in model.get("relationships", []) or []:
        source = relationship.get("sourceId") or relationship.get("source")
        target = relationship.get("destinationId") or relationship.get("destination")
        if source and target:
            edges.append((str(source), str(target)))
    if not node_ids:
        return None
    return node_ids, edges, [], "structurizr"


def parse_msadoc(raw):
    services = raw.get("services") if isinstance(raw, dict) else None
    if not isinstance(services, list):
        return None
    node_ids = []
    edges = []
    seen = set()
    for service in services:
        name = service.get("name")
        if not name:
            continue
        if name not in seen:
            seen.add(name)
            node_ids.append(name)
        for dependency in service.get("dependencies", []) or []:
            target = dependency if isinstance(dependency, str) else dependency.get("service")
            if target:
                edges.append((name, target))
    for _, target in edges:
        if target not in seen:
            seen.add(target)
            node_ids.append(target)
    if not node_ids:
        return None
    return node_ids, edges, [], "msadoc"


def parse_archunit(raw):
    if not isinstance(raw, dict):
        return None
    results = raw.get("results")
    if not isinstance(results, list):
        return None
    violations = []
    for result in results:
        if result.get("outcome") == "failed":
            violations.append(
                {
                    "rule": result.get("rule", result.get("name", "rule")),
                    "severity": "error",
                    "from": "",
                    "to": result.get("message", ""),
                }
            )
    return [], [], violations, "archunitnet"


def detect_and_parse(raw_path):
    text = raw_path.read_text(encoding="utf-8")
    parsed_json = None
    try:
        parsed_json = json.loads(text)
    except json.JSONDecodeError:
        parsed_json = None

    if parsed_json is not None:
        for parser in (
            parse_depcruise,
            parse_nx_graph,
            parse_structurizr,
            parse_msadoc,
            parse_archunit,
            parse_madge,
        ):
            result = parser(parsed_json)
            if result is not None:
                return result
    dot_result = parse_dot(text)
    if dot_result is not None:
        return dot_result
    return None


def status_from_violations(cycles, violations):
    hard = [v for v in violations if str(v.get("severity", "")).lower() in ("error", "blocking")]
    if hard:
        return "error", 4
    if cycles or violations:
        return "warn", 0
    return "ok", 0


def build_body(node_ids, edges, cycles, violations, metrics):
    body = [
        {
            "type": "metric-cards",
            "cards": [
                {"label": "Modules", "value": metrics["node_count"], "delta_metric": "node_count"},
                {"label": "Dependencies", "value": metrics["edge_count"], "delta_metric": "edge_count"},
                {"label": "Cycles", "value": metrics["cycle_count"], "delta_metric": "cycle_count"},
                {"label": "Max depth", "value": metrics["max_depth"], "delta_metric": "max_depth"},
            ],
        }
    ]

    cycle_members = set()
    for cycle in cycles:
        cycle_members.update(cycle)

    if len(node_ids) <= GRAPH_NODE_RENDER_LIMIT:
        graph_nodes = [
            {
                "id": node_id,
                "label": node_id.split("/")[-1] if "/" in node_id else node_id,
                "group": "cycle" if node_id in cycle_members else "module",
            }
            for node_id in node_ids
        ]
        graph_links = [{"source": source, "target": target} for source, target in edges]
        body.append(
            {
                "type": "d3-graph",
                "title": "Module dependency graph",
                "layout": "dag",
                "nodes": graph_nodes,
                "links": graph_links,
            }
        )
    else:
        body.append(
            {
                "type": "markdown",
                "title": "Module dependency graph",
                "md": (
                    f"Graph has {len(node_ids)} nodes, above the "
                    f"{GRAPH_NODE_RENDER_LIMIT}-node inline render limit. "
                    "Metrics and cycle/violation tables remain authoritative."
                ),
            }
        )

    if cycles:
        body.append(
            {
                "type": "table",
                "title": "Cycles",
                "filterable": True,
                "columns": [
                    {"key": "members", "label": "Members", "type": "string", "sortable": True},
                    {"key": "length", "label": "Length", "type": "number", "sortable": True},
                ],
                "rows": [
                    {"members": " → ".join(cycle + [cycle[0]]), "length": len(cycle)}
                    for cycle in cycles
                ],
                "defaultSort": {"key": "length", "dir": "desc"},
            }
        )

    if violations:
        body.append(
            {
                "type": "table",
                "title": "Rule violations",
                "filterable": True,
                "columns": [
                    {"key": "rule", "label": "Rule", "type": "string", "sortable": True},
                    {"key": "severity", "label": "Severity", "type": "string", "sortable": True},
                    {"key": "from", "label": "From", "type": "string", "sortable": True},
                    {"key": "to", "label": "To", "type": "string", "sortable": True},
                ],
                "rows": [
                    {
                        "rule": str(v.get("rule", "")),
                        "severity": str(v.get("severity", "")),
                        "from": str(v.get("from", "")),
                        "to": str(v.get("to", "")),
                    }
                    for v in violations
                ],
            }
        )
    return body


def main():
    if len(sys.argv) != 4:
        sys.stderr.write("usage: to-fragment.py <id> <raw_file> <out_fragment_json>\n")
        return 1

    fragment_id = sys.argv[1]
    raw_path = pathlib.Path(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])

    if not raw_path.is_file():
        sys.stderr.write(f"raw file not found: {raw_path}\n")
        return 2

    parsed = detect_and_parse(raw_path)
    if parsed is None:
        sys.stderr.write(f"unrecognized or unparseable architecture output: {raw_path}\n")
        return 2

    node_ids, edges, violations, tool_name = parsed
    node_set = list(dict.fromkeys(node_ids))
    adjacency = adjacency_from_edges(node_set, edges)
    cycles = cycles_from_components(tarjan_scc(adjacency))
    metrics = build_metrics(node_set, edges, cycles, adjacency)
    status, exit_code = status_from_violations(cycles, violations)

    summary = (
        f"{metrics['node_count']} modules, {metrics['edge_count']} dependencies, "
        f"{metrics['cycle_count']} cycles, max depth {metrics['max_depth']}."
    )

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": fragment_id,
        "category": "architecture",
        "title": "Architecture structure",
        "summary": summary,
        "status": status,
        "producer": {"skill": SKILL_NAME, "tool": tool_name, "version": "1"},
        "generated_at": now_iso(),
        "metrics": metrics,
        "body": build_body(node_set, edges, cycles, violations, metrics),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} status={status}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
