#!/usr/bin/env python3
"""Validate report fragments against the dev-report-fragment/v1 contract.

Usage: validate_fragments.py <fragments-dir>

Exit codes:
  0  every *.json fragment conforms
  1  bad arguments
  3  one or more fragments failed validation (per-file errors on stderr)

dev-report-build imports validate_dir from this module so the build and the
standalone validator never drift.
"""
import json
import pathlib
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"
CATEGORIES = {
    "architecture",
    "evolution",
    "dependencies",
    "quality",
    "security",
    "schema",
    "contracts",
    "mission",
}
STATUSES = {"ok", "info", "warn", "error"}
SECTION_TYPES = {
    "markdown",
    "table",
    "key-value",
    "metric-cards",
    "d3-graph",
    "sankey",
    "treemap",
    "heatmap",
    "mermaid",
}
ID_ALLOWED = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _is_str(value):
    return isinstance(value, str) and value != ""


def _is_obj(value):
    return isinstance(value, dict)


def _validate_section(section, index):
    errors = []
    where = f"body[{index}]"
    if not _is_obj(section):
        return [f"{where}: not an object"]
    section_type = section.get("type")
    if not _is_str(section_type):
        return [f"{where}: missing 'type'"]
    if section_type not in SECTION_TYPES:
        return errors
    if "title" in section and not isinstance(section["title"], str):
        errors.append(f"{where}: 'title' must be a string")

    if section_type == "markdown":
        if not _is_str(section.get("md")):
            errors.append(f"{where} (markdown): missing 'md' string")
    elif section_type == "table":
        columns = section.get("columns")
        rows = section.get("rows")
        if not isinstance(columns, list) or not columns:
            errors.append(f"{where} (table): 'columns' must be a non-empty array")
        else:
            for ci, column in enumerate(columns):
                if not _is_obj(column) or not _is_str(column.get("key")) or not _is_str(column.get("label")):
                    errors.append(f"{where} (table): columns[{ci}] needs 'key' and 'label'")
                elif column.get("type") not in ("string", "number"):
                    errors.append(f"{where} (table): columns[{ci}].type must be 'string' or 'number'")
        if not isinstance(rows, list):
            errors.append(f"{where} (table): 'rows' must be an array")
    elif section_type == "key-value":
        pairs = section.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            errors.append(f"{where} (key-value): 'pairs' must be a non-empty array")
        else:
            for pi, pair in enumerate(pairs):
                if not _is_obj(pair) or "k" not in pair or "v" not in pair:
                    errors.append(f"{where} (key-value): pairs[{pi}] needs 'k' and 'v'")
    elif section_type == "metric-cards":
        cards = section.get("cards")
        if not isinstance(cards, list) or not cards:
            errors.append(f"{where} (metric-cards): 'cards' must be a non-empty array")
        else:
            for ki, card in enumerate(cards):
                if not _is_obj(card) or not _is_str(card.get("label")) or "value" not in card:
                    errors.append(f"{where} (metric-cards): cards[{ki}] needs 'label' and 'value'")
    elif section_type == "d3-graph":
        nodes = section.get("nodes")
        links = section.get("links")
        if not isinstance(nodes, list) or not nodes:
            errors.append(f"{where} (d3-graph): 'nodes' must be a non-empty array")
        else:
            for ni, node in enumerate(nodes):
                if not _is_obj(node) or not _is_str(node.get("id")):
                    errors.append(f"{where} (d3-graph): nodes[{ni}] needs 'id'")
        if not isinstance(links, list):
            errors.append(f"{where} (d3-graph): 'links' must be an array")
        else:
            for li, link in enumerate(links):
                if not _is_obj(link) or "source" not in link or "target" not in link:
                    errors.append(f"{where} (d3-graph): links[{li}] needs 'source' and 'target'")
        if section.get("layout") not in ("force", "dag"):
            errors.append(f"{where} (d3-graph): 'layout' must be 'force' or 'dag'")
    elif section_type == "sankey":
        nodes = section.get("nodes")
        links = section.get("links")
        if not isinstance(nodes, list) or not nodes:
            errors.append(f"{where} (sankey): 'nodes' must be a non-empty array")
        if not isinstance(links, list) or not links:
            errors.append(f"{where} (sankey): 'links' must be a non-empty array")
        else:
            for li, link in enumerate(links):
                if not _is_obj(link) or "source" not in link or "target" not in link or "value" not in link:
                    errors.append(f"{where} (sankey): links[{li}] needs 'source', 'target', 'value'")
    elif section_type == "treemap":
        root = section.get("root")
        if not _is_obj(root) or not _is_str(root.get("name")):
            errors.append(f"{where} (treemap): 'root' must be an object with 'name'")
    elif section_type == "heatmap":
        x_labels = section.get("xLabels")
        y_labels = section.get("yLabels")
        cells = section.get("cells")
        if not isinstance(x_labels, list) or not x_labels:
            errors.append(f"{where} (heatmap): 'xLabels' must be a non-empty array")
        if not isinstance(y_labels, list) or not y_labels:
            errors.append(f"{where} (heatmap): 'yLabels' must be a non-empty array")
        if not isinstance(cells, list):
            errors.append(f"{where} (heatmap): 'cells' must be an array")
        else:
            for hi, cell in enumerate(cells):
                if not _is_obj(cell) or "x" not in cell or "y" not in cell or "v" not in cell:
                    errors.append(f"{where} (heatmap): cells[{hi}] needs 'x', 'y', 'v'")
        if section.get("colorScale") not in ("sequential", "diverging"):
            errors.append(f"{where} (heatmap): 'colorScale' must be 'sequential' or 'diverging'")
    elif section_type == "mermaid":
        if not _is_str(section.get("diagram")):
            errors.append(f"{where} (mermaid): missing 'diagram' string")
    return errors


def validate_fragment(fragment):
    errors = []
    if not _is_obj(fragment):
        return ["top level is not a JSON object"]

    if fragment.get("schema") != SCHEMA_VERSION:
        errors.append(f"'schema' must be '{SCHEMA_VERSION}'")

    fragment_id = fragment.get("id")
    if not _is_str(fragment_id):
        errors.append("'id' must be a non-empty string")
    elif any(character not in ID_ALLOWED for character in fragment_id):
        errors.append("'id' must match [a-z0-9-]+")

    if fragment.get("category") not in CATEGORIES:
        errors.append("'category' must be one of " + " | ".join(sorted(CATEGORIES)))

    if not _is_str(fragment.get("title")):
        errors.append("'title' must be a non-empty string")

    if not isinstance(fragment.get("summary"), str):
        errors.append("'summary' must be a string")

    if fragment.get("status") not in STATUSES:
        errors.append("'status' must be one of " + " | ".join(sorted(STATUSES)))

    if "severity" in fragment and fragment["severity"] is not None:
        severity = fragment["severity"]
        if not isinstance(severity, (int, float)) or isinstance(severity, bool) or not 0 <= severity <= 100:
            errors.append("'severity' must be a number 0-100 or null")

    producer = fragment.get("producer")
    if not _is_obj(producer):
        errors.append("'producer' must be an object")
    else:
        for key in ("skill", "tool", "version"):
            if not _is_str(producer.get(key)):
                errors.append(f"'producer.{key}' must be a non-empty string")

    if not _is_str(fragment.get("generated_at")):
        errors.append("'generated_at' must be a non-empty ISO-8601 string")

    if "metrics" in fragment:
        metrics = fragment["metrics"]
        if not _is_obj(metrics):
            errors.append("'metrics' must be an object")
        else:
            for key, value in metrics.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"'metrics.{key}' must be a number")

    body = fragment.get("body")
    if not isinstance(body, list):
        errors.append("'body' must be an array")
    else:
        for index, section in enumerate(body):
            errors.extend(_validate_section(section, index))

    return errors


def validate_dir(fragments_dir):
    fragments_dir = pathlib.Path(fragments_dir)
    if not fragments_dir.is_dir():
        return {"<dir>": [f"not a directory: {fragments_dir}"]}, []

    paths = sorted(fragments_dir.glob("*.json"))
    if not paths:
        return {"<dir>": [f"no *.json fragments in {fragments_dir}"]}, []

    failures = {}
    parsed = []
    seen_ids = {}
    for path in paths:
        try:
            fragment = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            failures[path.name] = [f"unreadable / invalid JSON: {error}"]
            continue
        errors = validate_fragment(fragment)
        fragment_id = fragment.get("id") if isinstance(fragment, dict) else None
        if isinstance(fragment_id, str) and fragment_id:
            if fragment_id in seen_ids:
                errors.append(f"duplicate id '{fragment_id}' (also in {seen_ids[fragment_id]})")
            else:
                seen_ids[fragment_id] = path.name
        if errors:
            failures[path.name] = errors
        else:
            parsed.append((path, fragment))
    return failures, parsed


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: validate_fragments.py <fragments-dir>\n")
        return 1

    failures, parsed = validate_dir(sys.argv[1])
    if failures:
        for name in sorted(failures):
            sys.stderr.write(f"{name}:\n")
            for message in failures[name]:
                sys.stderr.write(f"  - {message}\n")
        sys.stderr.write(f"FAIL {len(failures)} fragment(s) invalid\n")
        return 3

    print(f"OK {len(parsed)} fragment(s) valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
