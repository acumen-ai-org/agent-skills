#!/usr/bin/env python3
"""Normalize evolution raw outputs into dev-report-fragment/v1 JSON.

Usage:
  to-fragment.py evolution <out_dir>
  to-fragment.py author-activity <out_dir>
  to-fragment.py both <out_dir>

Reads the raw artifacts written by collect-history.sh / run-codemaat.sh /
run-git-of-theseus.sh / collect-author-activity.sh from <out_dir> and writes
<out_dir>/evolution.fragment.json and/or
<out_dir>/author-activity.fragment.json. Both fragments use category
"evolution". The script writes factual metrics{} and factual body[] only; the
references/*-narrative.md and *-classification.md roles enrich summary and
append narrative body[].

Each fragment declares its own top-menu groups via section "menu" labels.
evolution: the extension→folder→file tree under "Extension tree", per-pair and
code-maat churn under "Churn", the change-concentration treemap under
"Hotspots". author-activity: the per-author summary and author×type heatmap
under "Authors", the per-PR detail under "PRs". The metric-cards (and the
author-activity vibe-coder key-value) stay untagged so the renderer collects
them under the leading default group (the fragment title).

Exit codes:
  0  requested fragment(s) written
  1  bad arguments
  2  raw inputs present but unparseable; nothing written
  5  required raw bundle missing
"""
import csv
import datetime
import io
import json
import os
import pathlib
import subprocess
import sys

SCHEMA_VERSION = "dev-report-fragment/v1"

PR_TYPE_KEYS = [
    ("New feature", "new_feature_prs"),
    ("Updated feature", "updated_feature_prs"),
    ("Bug", "bug_prs"),
    ("Technical", "technical_prs"),
    ("Configuration", "configuration_prs"),
    ("Data", "data_prs"),
]


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path):
    rows = []
    text = path.read_text(encoding="utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        rows.append(row)
    return rows


def _modules_script():
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        candidate = pathlib.Path(plugin_root) / "scripts" / "modules.py"
        if candidate.is_file():
            return candidate
    return pathlib.Path(__file__).resolve().parents[3] / "scripts" / "modules.py"


class ModuleResolver:
    def __init__(self, repo):
        self._script = _modules_script()
        self._args = []
        if repo:
            config = pathlib.Path(repo) / "dev-process.json"
            if config.is_file():
                self._args = ["--config", str(config)]
        self._cache = {}

    def resolve(self, path):
        norm = (path or "").replace("\\", "/").strip("/")
        if not norm:
            return "root"
        if norm in self._cache:
            return self._cache[norm]
        result = subprocess.run(
            [sys.executable, str(self._script), "id", norm, *self._args],
            capture_output=True,
            text=True,
            check=False,
        )
        module_id = result.stdout.strip() if result.returncode == 0 else "root"
        if not module_id:
            module_id = "root"
        self._cache[norm] = module_id
        return module_id


def build_evolution(out_dir):
    history_path = out_dir / "history.json"
    if not history_path.is_file():
        sys.stderr.write(f"missing required {history_path}\n")
        return None, 5
    try:
        history = _read_json(history_path)
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unparseable history.json: {error}\n")
        return None, 2

    pairs = history.get("pairs", [])
    total_files_changed = sum(int(p.get("files_changed", 0)) for p in pairs)
    total_added = sum(int(p.get("lines_added", 0)) for p in pairs)
    total_removed = sum(int(p.get("lines_removed", 0)) for p in pairs)

    extension_totals = {}
    for pair in pairs:
        for extension, count in pair.get("by_extension", {}).items():
            extension_totals[extension] = extension_totals.get(extension, 0) + int(count)

    coupling_count = 0
    coupling_path = out_dir / "codemaat-coupling.csv"
    churn_rows = []
    if coupling_path.is_file():
        try:
            coupling_count = len(_read_csv(coupling_path))
        except (OSError, csv.Error):
            coupling_count = 0
    churn_path = out_dir / "codemaat-churn.csv"
    if churn_path.is_file():
        try:
            churn_rows = _read_csv(churn_path)
        except (OSError, csv.Error):
            churn_rows = []

    metrics = {
        "release_pairs": len(pairs),
        "files_changed_total": total_files_changed,
        "lines_added_total": total_added,
        "lines_removed_total": total_removed,
        "coupling_pairs": coupling_count,
        "extensions_touched": len(extension_totals),
    }

    resolver = ModuleResolver(history.get("repo"))

    extension_tree = history.get("extension_tree", [])
    extension_tree_rows = []
    for ext_node in extension_tree:
        folder_rows = []
        for folder_node in ext_node.get("folders", []):
            file_rows = [
                {
                    "name": file_node.get("file", ""),
                    "files_changed": int(file_node.get("files_changed", 0)),
                    "module": resolver.resolve(file_node.get("path", "")),
                }
                for file_node in folder_node.get("files", [])
            ]
            folder_rows.append(
                {
                    "name": folder_node.get("folder", ""),
                    "files_changed": int(folder_node.get("files_changed", 0)),
                    "module": resolver.resolve(folder_node.get("path", "")),
                    "children": file_rows,
                }
            )
        extension_tree_rows.append(
            {
                "name": ext_node.get("extension", ""),
                "files_changed": int(ext_node.get("files_changed", 0)),
                "module": "",
                "children": folder_rows,
            }
        )

    if not extension_tree_rows:
        extension_tree_rows = [
            {"name": extension, "files_changed": count, "module": ""}
            for extension, count in sorted(
                extension_totals.items(), key=lambda kv: (-kv[1], kv[0])
            )
        ]

    pair_rows = [
        {
            "pair": pair.get("pair", ""),
            "files_changed": int(pair.get("files_changed", 0)),
            "lines_added": int(pair.get("lines_added", 0)),
            "lines_removed": int(pair.get("lines_removed", 0)),
        }
        for pair in pairs
    ]

    treemap_children = [
        {"name": extension, "value": count}
        for extension, count in sorted(
            extension_totals.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]

    body = [
        {
            "type": "metric-cards",
            "cards": [
                {"label": "Release pairs", "value": len(pairs), "delta_metric": "release_pairs"},
                {"label": "Files changed", "value": total_files_changed, "delta_metric": "files_changed_total"},
                {"label": "Coupling pairs", "value": coupling_count, "delta_metric": "coupling_pairs"},
            ],
        },
        {
            "type": "table",
            "title": "Files changed by extension → folder → file",
            "view": "release",
            "menu": "Extension tree",
            "filterable": True,
            "columns": [
                {"key": "name", "label": "Extension / folder / file", "type": "string", "sortable": True},
                {"key": "files_changed", "label": "Files changed", "type": "number", "sortable": True},
                {"key": "module", "label": "Module", "type": "module", "sortable": True},
            ],
            "rows": extension_tree_rows,
            "defaultSort": {"key": "files_changed", "dir": "desc"},
        },
        {
            "type": "table",
            "title": "Per-release-pair churn (change vs production)",
            "view": "production",
            "menu": "Churn",
            "columns": [
                {"key": "pair", "label": "Release pair", "type": "string", "sortable": True},
                {"key": "files_changed", "label": "Files changed", "type": "number", "sortable": True},
                {"key": "lines_added", "label": "Lines added", "type": "number", "sortable": True},
                {"key": "lines_removed", "label": "Lines removed", "type": "number", "sortable": True},
            ],
            "rows": pair_rows,
        },
        {
            "type": "treemap",
            "title": "Change concentration by extension",
            "view": "release",
            "menu": "Hotspots",
            "root": {"name": "changed files", "children": treemap_children}
            if treemap_children
            else {"name": "changed files", "value": 0},
        },
    ]

    if churn_rows:
        churn_columns = list(churn_rows[0].keys())
        body.append(
            {
                "type": "table",
                "title": "code-maat churn (change vs production)",
                "view": "production",
                "menu": "Churn",
                "filterable": True,
                "columns": [
                    {
                        "key": column,
                        "label": column,
                        "type": "number" if column != churn_columns[0] else "string",
                        "sortable": True,
                    }
                    for column in churn_columns
                ],
                "rows": [
                    {
                        column: (
                            int(row[column])
                            if column != churn_columns[0] and str(row[column]).lstrip("-").isdigit()
                            else row[column]
                        )
                        for column in churn_columns
                    }
                    for row in churn_rows
                ],
            }
        )

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "evolution",
        "category": "evolution",
        "title": "Repository evolution",
        "summary": (
            f"{len(pairs)} release pair(s), {total_files_changed} files changed, "
            f"{coupling_count} coupled file pair(s)."
        ),
        "status": "ok",
        "producer": {
            "skill": "dev-analysis-evolution",
            "tool": "collect-history+code-maat+git-of-theseus",
            "version": "1",
        },
        "generated_at": _now(),
        "metrics": metrics,
        "body": body,
    }
    return fragment, 0


def build_author_activity(out_dir):
    bundle_path = out_dir / "author-activity.json"
    if not bundle_path.is_file():
        sys.stderr.write(f"missing required {bundle_path}\n")
        return None, 5
    try:
        bundle = _read_json(bundle_path)
    except (json.JSONDecodeError, OSError) as error:
        sys.stderr.write(f"unparseable author-activity.json: {error}\n")
        return None, 2

    classified_path = out_dir / "author-activity.classified.json"
    classified = None
    if classified_path.is_file():
        try:
            classified = _read_json(classified_path)
        except (json.JSONDecodeError, OSError):
            classified = None

    pr_units = (classified or bundle).get("pr_units", [])
    resolver = ModuleResolver(bundle.get("repo"))

    type_counts = {label: 0 for label, _ in PR_TYPE_KEYS}
    pattern_counts = {"New patterns": 0, "Existing patterns, components and modules": 0}
    per_author = {}
    detail_rows = []
    pr_types_seen = []

    for unit in pr_units:
        author = unit.get("author") or unit.get("raw_author_name") or "(unknown)"
        pr_type = unit.get("pr_type", "")
        pattern_use = unit.get("pattern_use", "")
        if pr_type in type_counts:
            type_counts[pr_type] += 1
        if pr_type and pr_type not in pr_types_seen:
            pr_types_seen.append(pr_type)
        if pattern_use in pattern_counts:
            pattern_counts[pattern_use] += 1

        author_record = per_author.setdefault(
            author,
            {"author": author, "prs": 0, "type_breakdown": {}},
        )
        author_record["prs"] += 1
        if pr_type:
            author_record["type_breakdown"][pr_type] = (
                author_record["type_breakdown"].get(pr_type, 0) + 1
            )

        work_items = unit.get("work_items", [])
        work_item_ids = ", ".join(
            "#" + str(item.get("id"))
            for item in work_items
            if isinstance(item, dict) and item.get("id") is not None
        )
        seen_modules = []
        for path in unit.get("changed_paths", []):
            module = resolver.resolve(path)
            if module not in seen_modules:
                seen_modules.append(module)
        if not seen_modules:
            seen_modules = [""]
        for module in sorted(seen_modules):
            detail_rows.append(
                {
                    "pr": unit.get("pr") if unit.get("pr") is not None else 0,
                    "title": unit.get("title", ""),
                    "author": author,
                    "module": module,
                    "type": pr_type or "(unclassified)",
                    "pattern_use": pattern_use or "",
                    "work_items": work_item_ids,
                }
            )

    vibe_definition = bundle.get("vibe_coder_definition")
    vibe_coders = 0
    if classified:
        vibe_coders = int(classified.get("vibe_coders", 0))

    metrics = {
        "pr_total": len(pr_units),
        "authors": len(per_author),
        "new_pattern_prs": pattern_counts["New patterns"],
        "existing_pattern_prs": pattern_counts["Existing patterns, components and modules"],
    }
    for label, key in PR_TYPE_KEYS:
        metrics[key] = type_counts[label]
    if vibe_definition is not None:
        metrics["vibe_coders"] = vibe_coders

    author_rows = []
    for author, record in sorted(
        per_author.items(), key=lambda kv: (-kv[1]["prs"], kv[0])
    ):
        row = {"author": author, "prs": record["prs"]}
        for label, _ in PR_TYPE_KEYS:
            row[label] = record["type_breakdown"].get(label, 0)
        author_rows.append(row)

    author_columns = [
        {"key": "author", "label": "Author", "type": "string", "sortable": True},
        {"key": "prs", "label": "PRs", "type": "number", "sortable": True},
    ]
    for label, _ in PR_TYPE_KEYS:
        author_columns.append(
            {"key": label, "label": label, "type": "number", "sortable": True}
        )

    heatmap_x = [label for label, _ in PR_TYPE_KEYS]
    heatmap_y = [row["author"] for row in author_rows] or ["(none)"]
    heatmap_cells = []
    for author, record in per_author.items():
        for label, _ in PR_TYPE_KEYS:
            value = record["type_breakdown"].get(label, 0)
            if value:
                heatmap_cells.append({"x": label, "y": author, "v": value})

    vibe_summary = (
        f"{vibe_coders} vibe coder(s)"
        if vibe_definition is not None
        else "undetermined — no repository definition found"
    )

    body = [
        {
            "type": "metric-cards",
            "cards": [
                {"label": "PRs", "value": len(pr_units), "delta_metric": "pr_total"},
                {"label": "Authors", "value": len(per_author), "delta_metric": "authors"},
                {
                    "label": "New-pattern PRs",
                    "value": pattern_counts["New patterns"],
                    "delta_metric": "new_pattern_prs",
                },
            ],
        },
        {
            "type": "key-value",
            "title": "Vibe coder",
            "pairs": [{"k": "Status", "v": vibe_summary}],
        },
        {
            "type": "table",
            "title": "Per-author summary",
            "menu": "Authors",
            "filterable": True,
            "columns": author_columns,
            "rows": author_rows,
            "defaultSort": {"key": "prs", "dir": "desc"},
        },
        {
            "type": "table",
            "title": "Per-PR detail",
            "menu": "PRs",
            "filterable": True,
            "columns": [
                {"key": "pr", "label": "PR", "type": "number", "sortable": True},
                {"key": "title", "label": "Title", "type": "string", "sortable": True},
                {"key": "author", "label": "Author", "type": "string", "sortable": True},
                {"key": "module", "label": "Module", "type": "module", "sortable": True},
                {"key": "type", "label": "Type", "type": "string", "sortable": True},
                {"key": "pattern_use", "label": "Pattern use", "type": "string", "sortable": True},
                {"key": "work_items", "label": "Work items", "type": "string", "sortable": True},
            ],
            "rows": detail_rows,
            "defaultSort": {"key": "pr", "dir": "desc"},
        },
        {
            "type": "heatmap",
            "title": "Author × PR type",
            "menu": "Authors",
            "colorScale": "sequential",
            "xLabels": heatmap_x,
            "yLabels": heatmap_y,
            "cells": heatmap_cells,
        },
    ]

    fragment = {
        "schema": SCHEMA_VERSION,
        "id": "author-activity",
        "category": "evolution",
        "title": "Per-author activity",
        "summary": (
            f"{len(pr_units)} PR-unit(s) across {len(per_author)} author(s); "
            f"vibe coder: {vibe_summary}."
        ),
        "status": "ok",
        "producer": {
            "skill": "dev-analysis-evolution",
            "tool": "collect-author-activity",
            "version": "1",
        },
        "generated_at": _now(),
        "metrics": metrics,
        "body": body,
    }
    return fragment, 0


def main():
    if len(sys.argv) != 3:
        sys.stderr.write(
            "usage: to-fragment.py <evolution|author-activity|both> <out_dir>\n"
        )
        return 1

    target = sys.argv[1]
    out_dir = pathlib.Path(sys.argv[2])
    if not out_dir.is_dir():
        sys.stderr.write(f"not a directory: {out_dir}\n")
        return 1
    if target not in ("evolution", "author-activity", "both"):
        sys.stderr.write(
            "first argument must be evolution, author-activity, or both\n"
        )
        return 1

    builders = []
    if target in ("evolution", "both"):
        builders.append(("evolution.fragment.json", build_evolution))
    if target in ("author-activity", "both"):
        builders.append(("author-activity.fragment.json", build_author_activity))

    written = []
    for filename, builder in builders:
        fragment, code = builder(out_dir)
        if code != 0:
            return code
        path = out_dir / filename
        path.write_text(
            json.dumps(fragment, indent=2, sort_keys=True), encoding="utf-8"
        )
        written.append(path.name)

    print("wrote " + ", ".join(written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
