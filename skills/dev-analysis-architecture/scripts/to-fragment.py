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
  - collect-structure.py  tool-free source scan (kind architecture-source)
  - structure-from-source.md  role payload (kind architecture-source-role)

The graph becomes a d3-graph body; metrics carry node_count, edge_count,
cycle_count, max_depth; any reported violation drives status (warn for
cycles/soft rule findings, error for hard layering violations) and exit 4.
The tool-free raw additionally carries an import-flow sankey, a per-file
listing table, and — when the repo resolves to two or more modules with
inter-module edges — a C4 mermaid. body[0] is an untagged Summary markdown
that leads the default menu group, followed by the untagged metric-cards.
Sections carry a top-menu group via "menu": the dependency graph and its
per-file listing under "Dependency graph", cycles under "Cycles", rule
violations under "Rules", the import-flow sankey under "Flow", the C4 mermaid
under "C4". The Summary and metric-cards stay untagged so the renderer
collects them under the leading default group (the fragment title). The
listing table carries a type:"module" column whose ids come from the shared
scripts/modules.py resolver (config from the raw's repo/config location). When
the repo defines a non-empty modules set the d3-graph and sankey collapse to
module granularity; otherwise they stay at file/package granularity. The C4
mermaid is module-level by construction.

Exit codes:
  0  fragment written; status ok or warn
  1  bad arguments
  2  raw output unparseable; nothing written
  4  fragment written with status error (blocking violations)
"""
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"
SKILL_NAME = "dev-analysis-architecture"
GRAPH_NODE_RENDER_LIMIT = 300


def plugin_root():
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parents[3]


def resolve_modules(paths, config):
    resolver = plugin_root() / "scripts" / "modules.py"
    ids = {}
    if not resolver.is_file():
        return {path: "root" for path in paths}
    for path in paths:
        command = [sys.executable, str(resolver), "id", path]
        if config:
            command += ["--config", config]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        module_id = completed.stdout.strip() if completed.returncode == 0 else ""
        ids[path] = module_id or "root"
    return ids


def module_count(repo, config):
    if not config:
        return 0
    resolver = plugin_root() / "scripts" / "modules.py"
    if not resolver.is_file():
        return 0
    command = [sys.executable, str(resolver), "list", "--config", config]
    if repo:
        command += ["--repo", repo]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return 0
    modules = [line for line in completed.stdout.splitlines() if line.strip()]
    non_root = [module for module in modules if module != "root"]
    return len(non_root)


def _report_help():
    path = pathlib.Path(__file__).resolve().parent.parent / "references" / "report-help.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


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


def parse_source_inventory(raw):
    if not isinstance(raw, dict):
        return None
    if raw.get("kind") not in ("architecture-source", "architecture-source-role"):
        return None
    raw_nodes = raw.get("nodes")
    raw_edges = raw.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        return None
    node_ids = []
    node_meta = {}
    seen = set()
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        identifier = node.get("id")
        if not isinstance(identifier, str) or identifier in seen:
            continue
        seen.add(identifier)
        node_ids.append(identifier)
        node_meta[identifier] = {
            "label": node.get("label") if isinstance(node.get("label"), str) else identifier,
            "group": node.get("group") if isinstance(node.get("group"), str) else "module",
        }
    edges = []
    weights = {}
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        for member in (source, target):
            if member not in seen:
                seen.add(member)
                node_ids.append(member)
                node_meta[member] = {"label": member.split("/")[-1], "group": "module"}
        try:
            value = int(edge.get("value", 1))
        except (TypeError, ValueError):
            value = 1
        value = max(1, value)
        edges.append((source, target))
        weights[(source, target)] = weights.get((source, target), 0) + value
    layout = raw.get("layout")
    if layout not in ("force", "dag", "chord"):
        layout = None
    c4_mermaid = raw.get("c4_mermaid") if isinstance(raw.get("c4_mermaid"), str) else None
    stacks = raw.get("stacks") if isinstance(raw.get("stacks"), list) else []
    repo = raw.get("repo") if isinstance(raw.get("repo"), str) else None
    config = raw.get("config") if isinstance(raw.get("config"), str) else None
    if config is None and repo is not None:
        candidate = pathlib.Path(repo) / "dev-process.json"
        if candidate.is_file():
            config = str(candidate)
    extra = {
        "node_meta": node_meta,
        "weights": weights,
        "layout": layout,
        "c4_mermaid": c4_mermaid,
        "stacks": stacks,
        "repo": repo,
        "config": config,
    }
    return node_ids, edges, [], "collect-structure", extra


def detect_and_parse(raw_path):
    text = raw_path.read_text(encoding="utf-8")
    parsed_json = None
    try:
        parsed_json = json.loads(text)
    except json.JSONDecodeError:
        parsed_json = None

    if parsed_json is not None:
        source_result = parse_source_inventory(parsed_json)
        if source_result is not None:
            return source_result
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
                return result + (None,)
    dot_result = parse_dot(text)
    if dot_result is not None:
        return dot_result + (None,)
    return None


def status_from_violations(cycles, violations):
    hard = [v for v in violations if str(v.get("severity", "")).lower() in ("error", "blocking")]
    if hard:
        return "error", 4
    if cycles or violations:
        return "warn", 0
    return "ok", 0


MENU_GRAPH = "Dependency graph"
MENU_CYCLES = "Cycles"
MENU_RULES = "Rules"
MENU_FLOW = "Flow"
MENU_C4 = "C4"


def build_body(node_ids, edges, cycles, violations, metrics, summary, extra=None):
    body = [
        {"type": "markdown", "title": "Summary", "md": summary},
        {
            "type": "metric-cards",
            "cards": [
                {"label": "Modules", "value": metrics["node_count"], "delta_metric": "node_count"},
                {"label": "Dependencies", "value": metrics["edge_count"], "delta_metric": "edge_count"},
                {"label": "Cycles", "value": metrics["cycle_count"], "delta_metric": "cycle_count"},
                {"label": "Max depth", "value": metrics["max_depth"], "delta_metric": "max_depth"},
            ],
        },
    ]

    cycle_members = set()
    for cycle in cycles:
        cycle_members.update(cycle)

    node_meta = extra.get("node_meta") if extra else None
    weights = extra.get("weights") if extra else None
    layout = (extra.get("layout") if extra else None) or "dag"

    module_ids = None
    repo = extra.get("repo") if extra else None
    config = extra.get("config") if extra else None
    if extra is not None and config and module_count(repo, config) >= 1:
        module_ids = resolve_modules([nid for nid in node_ids if nid], config)

    graph_node_ids, graph_edges, graph_weights, graph_meta = _graph_view(
        node_ids, edges, weights, node_meta, module_ids
    )

    if not graph_node_ids:
        body.append(
            {
                "type": "markdown",
                "menu": MENU_GRAPH,
                "title": "Module dependency graph",
                "status": "info",
                "md": (
                    "The analyzer reported rule findings without a module "
                    "graph. The metrics and the rule-violation table remain "
                    "authoritative."
                ),
            }
        )
    elif len(graph_node_ids) <= GRAPH_NODE_RENDER_LIMIT:
        graph_nodes = []
        for node_id in graph_node_ids:
            if node_id in cycle_members:
                group = "cycle"
            elif graph_meta and node_id in graph_meta:
                group = graph_meta[node_id]["group"]
            else:
                group = "module"
            if graph_meta and node_id in graph_meta:
                label = graph_meta[node_id]["label"]
            else:
                label = node_id.split("/")[-1] if "/" in node_id else node_id
            graph_nodes.append({"id": node_id, "label": label, "group": group})
        graph_links = []
        for source, target in dict.fromkeys(graph_edges):
            link = {"source": source, "target": target}
            if graph_weights and (source, target) in graph_weights:
                link["value"] = graph_weights[(source, target)]
            graph_links.append(link)
        body.append(
            {
                "type": "d3-graph",
                "menu": MENU_GRAPH,
                "title": "Module dependency graph",
                "status": "info",
                "help": "Boxes are modules, arrows are import edges; cycle members are grouped apart.",
                "layout": layout,
                "nodes": graph_nodes,
                "links": graph_links,
            }
        )
    else:
        body.append(
            {
                "type": "markdown",
                "menu": MENU_GRAPH,
                "title": "Module dependency graph",
                "status": "info",
                "md": (
                    f"Graph has {len(graph_node_ids)} nodes, above the "
                    f"{GRAPH_NODE_RENDER_LIMIT}-node inline render limit. "
                    "Metrics and cycle/violation tables remain authoritative."
                ),
            }
        )

    if cycles:
        body.append(
            {
                "type": "table",
                "menu": MENU_CYCLES,
                "title": "Cycles",
                "status": "warn",
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
        violation_status, _ = status_from_violations([], violations)
        body.append(
            {
                "type": "table",
                "menu": MENU_RULES,
                "title": "Rule violations",
                "status": violation_status,
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

    if extra is not None:
        body.extend(
            _source_sections(
                node_ids, edges, weights, node_meta, extra, module_ids
            )
        )
    return body


def _graph_view(node_ids, edges, weights, node_meta, module_ids):
    if not module_ids:
        return node_ids, edges, weights, node_meta
    order = []
    seen = set()
    new_meta = {}
    for node_id in node_ids:
        mid = module_ids.get(node_id, "root")
        if mid not in seen:
            seen.add(mid)
            order.append(mid)
            new_meta[mid] = {"label": mid, "group": mid}
    new_weights = {}
    new_edges = []
    edge_seen = set()
    for source, target in edges:
        src = module_ids.get(source, "root")
        dst = module_ids.get(target, "root")
        if src == dst:
            continue
        weight = weights.get((source, target), 1) if weights else 1
        new_weights[(src, dst)] = new_weights.get((src, dst), 0) + weight
        if (src, dst) not in edge_seen:
            edge_seen.add((src, dst))
            new_edges.append((src, dst))
    return order, new_edges, new_weights, new_meta


def _source_sections(node_ids, edges, weights, node_meta, extra, module_ids):
    sections = []

    def group_of(node_id):
        if module_ids:
            return module_ids.get(node_id, "root")
        if node_meta and node_id in node_meta:
            return node_meta[node_id]["group"]
        return group_root(node_id)

    cross = {}
    for source, target in edges:
        weight = weights.get((source, target), 1) if weights else 1
        src_group = group_of(source)
        dst_group = group_of(target)
        if src_group != dst_group:
            cross[(src_group, dst_group)] = cross.get((src_group, dst_group), 0) + weight

    if cross:
        flow = cross
        flow_title = "Import flow between modules" if module_ids else "Import flow between packages"
    else:
        flow = {}
        for source, target in edges:
            weight = weights.get((source, target), 1) if weights else 1
            flow[(source, target)] = flow.get((source, target), 0) + weight
        flow = _break_back_edges(flow)
        flow_title = "Import flow"

    if flow:
        flow_node_ids = []
        seen = set()
        for src_node, dst_node in flow:
            for member in (src_node, dst_node):
                if member not in seen:
                    seen.add(member)
                    flow_node_ids.append(member)

        def flow_label(node_id):
            if cross:
                return node_id
            if node_meta and node_id in node_meta:
                return node_meta[node_id]["label"]
            return node_id.split("/")[-1] if "/" in node_id else node_id

        sections.append(
            {
                "type": "sankey",
                "menu": MENU_FLOW,
                "title": flow_title,
                "status": "info",
                "nodes": [{"id": nid, "label": flow_label(nid)} for nid in flow_node_ids],
                "links": [
                    {"source": src_node, "target": dst_node, "value": value}
                    for (src_node, dst_node), value in sorted(flow.items())
                ],
            }
        )

    c4_mermaid = extra.get("c4_mermaid") or _c4_from_modules(edges, module_ids)
    if c4_mermaid:
        sections.append(
            {
                "type": "mermaid",
                "menu": MENU_C4,
                "title": "C4 context / container",
                "status": "info",
                "diagram": c4_mermaid,
            }
        )

    config = extra.get("config")
    listing_paths = [nid for nid in node_ids if nid]
    listing_modules = (
        module_ids
        if module_ids is not None
        else resolve_modules(sorted(set(listing_paths)), config)
    )

    if listing_paths:
        sections.append(
            {
                "type": "table",
                "menu": MENU_GRAPH,
                "title": "Source files by module",
                "filterable": True,
                "columns": [
                    {"key": "file", "label": "File", "type": "string", "sortable": True},
                    {"key": "package", "label": "Package", "type": "string", "sortable": True},
                    {"key": "module", "label": "Module", "type": "module", "sortable": True},
                ],
                "rows": [
                    {
                        "file": nid,
                        "package": (
                            node_meta[nid]["group"]
                            if node_meta and nid in node_meta
                            else group_root(nid)
                        ),
                        "module": listing_modules.get(nid, "root"),
                    }
                    for nid in listing_paths
                ],
                "defaultSort": {"key": "file", "dir": "asc"},
            }
        )
    return sections


def group_root(node_id):
    return node_id.split("/")[0] if "/" in node_id else "."


def _break_back_edges(flow):
    order = {}
    nodes = []
    for source, target in flow:
        for member in (source, target):
            if member not in order:
                order[member] = len(nodes)
                nodes.append(member)
    acyclic = {}
    for (source, target), value in flow.items():
        if order[source] < order[target]:
            acyclic[(source, target)] = value
    return acyclic if acyclic else flow


def _c4_from_modules(edges, module_ids):
    if not module_ids:
        return None
    modules = []
    seen = set()
    for value in module_ids.values():
        if value not in seen:
            seen.add(value)
            modules.append(value)
    if len(modules) < 2:
        return None
    module_edges = set()
    for source, target in edges:
        src = module_ids.get(source, "root")
        dst = module_ids.get(target, "root")
        if src != dst:
            module_edges.add((src, dst))
    if not module_edges:
        return None
    alias = {module: f"c{index}" for index, module in enumerate(modules)}
    lines = ["flowchart TD", '  subgraph System["System (modules)"]']
    for module in modules:
        lines.append(f'    {alias[module]}["{module}"]')
    lines.append("  end")
    for src_module, dst_module in sorted(module_edges):
        lines.append(f"  {alias[src_module]} --> {alias[dst_module]}")
    return "\n".join(lines)


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

    node_ids, edges, violations, tool_name, extra = parsed
    node_set = list(dict.fromkeys(node_ids))
    adjacency = adjacency_from_edges(node_set, edges)
    cycles = cycles_from_components(tarjan_scc(adjacency))
    metrics = build_metrics(node_set, edges, cycles, adjacency)
    status, exit_code = status_from_violations(cycles, violations)

    summary = (
        f"{metrics['node_count']} modules, {metrics['edge_count']} dependencies, "
        f"{metrics['cycle_count']} cycles, max depth {metrics['max_depth']}."
    )
    if extra is not None:
        summary += " Source-scanned (no analyzer)."

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
        "body": build_body(node_set, edges, cycles, violations, metrics, summary, extra),
    }

    help_md = _report_help()
    if help_md:
        fragment["help"] = help_md

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fragment, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} status={status}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
