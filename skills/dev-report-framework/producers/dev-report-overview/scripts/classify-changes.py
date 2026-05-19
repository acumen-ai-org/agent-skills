#!/usr/bin/env python3
"""Deterministically classify a release's commits into change groups and
architectural-shift signals — no model, no network.

Usage:
  classify-changes.py --commits <commits.txt> --changed <changed-files.txt>
      [--classified <author-activity.classified.json>]
      [--config <dev-process.json>] [--repo <dir>]
      --out <changes_shifts.json>

  --commits     scope.sh's commits.txt: one "<sha>\\t<subject>" per line.
  --changed     scope.sh's changed-files.txt: git diff --name-status lines.
  --classified  optional dev-analysis-evolution author-activity.classified.json
                (pr_units[] with pr_type / work_items[].type).
  --config      optional dev-process.json carrying a "modules" array; used to
                fold a shift's files onto module ids.
  --repo        optional repo root, only used to list module dirs.
  --out         where the changes_shifts.json document is written.

Output document:
  { "changes": { "groups": [ {"type","count","subjects":[...]} ] },
    "shifts":  { "rows":   [ {"shift","signal","modules":[...]} ] } }

Exit codes:
  0  written
  1  bad arguments
  2  an input was unreadable
"""
import argparse
import json
import os
import pathlib
import re
import sys

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT")
if _PLUGIN_ROOT:
    _MODULES_DIR = pathlib.Path(_PLUGIN_ROOT) / "scripts"
else:
    _MODULES_DIR = (
        pathlib.Path(__file__).resolve().parents[3] / "scripts"
    )
if str(_MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULES_DIR))
try:
    import modules as _modules
except ImportError:
    _modules = None

CONVENTIONAL = {
    "feat": "feature",
    "feature": "feature",
    "fix": "bugfix",
    "bugfix": "bugfix",
    "refactor": "refactor",
    "chore": "chore",
    "docs": "documentation",
    "doc": "documentation",
    "test": "tests",
    "tests": "tests",
    "perf": "performance",
    "infra": "infrastructure",
    "build": "infrastructure",
    "ci": "infrastructure",
    "breaking": "breaking",
}
WORK_ITEM_TYPE = {
    "bug": "bugfix",
    "story": "feature",
    "feature": "feature",
    "user story": "feature",
    "epic": "feature",
}
GROUP_ORDER = [
    "breaking",
    "feature",
    "enhancement",
    "bugfix",
    "refactor",
    "performance",
    "infrastructure",
    "tests",
    "documentation",
    "chore",
    "other",
]
SHIFT_ORDER = [
    "auth & identity",
    "public API contract",
    "data model / schema",
    "dependency upgrades",
    "build & CI",
    "configuration & secrets",
    "cross-cutting",
    "module / service boundaries",
    "performance",
    "security hardening",
    "submodule pointer bumps",
    "tooling / agents",
]
SUBJECT_CAP = 8


def _read_lines(path):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    return [line for line in text.splitlines() if line.strip()]


def _parse_commits(lines):
    commits = []
    for line in lines:
        if "\t" in line:
            sha, subject = line.split("\t", 1)
        else:
            sha, subject = "", line
        commits.append((sha.strip(), subject.strip()))
    return commits


def _parse_changed(lines):
    paths = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0].strip()
        if status[:1] in ("R", "C") and len(parts) >= 3:
            paths.append((status, parts[2].strip()))
        else:
            paths.append((status, parts[1].strip()))
    return paths


def _conventional_type(subject):
    head = subject.strip()
    low = head.lower()
    if low.startswith("breaking change"):
        return "breaking"
    match = re.match(r"^([a-z]+)(\([^)]*\))?(!)?:", low)
    if not match:
        return None
    if match.group(3) == "!":
        return "breaking"
    return CONVENTIONAL.get(match.group(1))


def _classified_units(classified_path):
    try:
        data = json.loads(
            pathlib.Path(classified_path).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        units = data.get("pr_units")
        if isinstance(units, list):
            return units
    return []


def _unit_type(unit):
    pr_type = (unit.get("pr_type") or "").strip().lower()
    if pr_type in ("bug",):
        return "bugfix"
    if pr_type in ("new feature", "updated feature"):
        return "feature"
    if pr_type in ("technical",):
        return "refactor"
    if pr_type in ("configuration",):
        return "infrastructure"
    if pr_type in ("data",):
        return "feature"
    for item in unit.get("work_items", []):
        if not isinstance(item, dict):
            continue
        wt = (item.get("type") or "").strip().lower()
        mapped = WORK_ITEM_TYPE.get(wt)
        if mapped:
            return mapped
    return None


def _heuristic_type(paths):
    if not paths:
        return "other"
    names = [p for _, p in paths]

    def is_test(name):
        low = name.lower()
        return (
            "test" in low
            or "/__tests__/" in low
            or low.endswith(".spec.ts")
            or low.endswith(".spec.js")
        )

    def is_doc(name):
        low = name.lower()
        return low.endswith(".md") or low.endswith(".rst") or "/docs/" in low

    def is_ci(name):
        low = name.lower()
        return (
            ".github/" in low
            or "azure-pipelines" in low
            or low.endswith("dockerfile")
            or "/ci/" in low
            or low.endswith(".yml")
            or low.endswith(".yaml")
        )

    if all(is_test(n) for n in names):
        return "tests"
    if all(is_doc(n) for n in names):
        return "documentation"
    if all(is_ci(n) for n in names):
        return "infrastructure"
    statuses = {s for s, _ in paths}
    if statuses and all(s[:1] in ("R", "C") for s in statuses):
        return "refactor"
    if any(s[:1] == "A" for s, _ in paths):
        return "feature"
    return "enhancement"


_MAJOR_DEP = re.compile(r"\.(csproj|props|targets)$|package-lock\.json$|package\.json$|requirements.*\.txt$|go\.mod$|Cargo\.toml$", re.I)
_CONFIG_FILE = re.compile(r"appsettings.*\.json$|\.env(\.|$)|/config/|secrets|\.ini$|\.toml$", re.I)
_AUTH_FILE = re.compile(r"auth|identity|login|oauth|token|jwt|session", re.I)
_API_FILE = re.compile(r"controller|/api/|endpoint|\.proto$|openapi|swagger|/contracts?/", re.I)
_SCHEMA_FILE = re.compile(r"migration|schema|/models?/|\.sql$|entit(y|ies)|dbcontext", re.I)
_CI_FILE = re.compile(r"\.github/|azure-pipelines|dockerfile|/ci/|\.gitlab-ci", re.I)
_CROSS_FILE = re.compile(r"logg(ing|er)|telemetry|tracing|metrics|errorhandl|exception", re.I)
_PERF_FILE = re.compile(r"cache|index|perf|benchmark|optimi[sz]", re.I)
_SECURITY_FILE = re.compile(r"security|crypto|sanitiz|escap|csrf|xss|vulnerab", re.I)
_TOOLING_FILE = re.compile(r"\.claude/|/agents?/|/skills?/|/scripts?/|/tools?/", re.I)


def _shift_signals(paths):
    fired = {}

    def add(shift, signal, name, breaking=False):
        bucket = fired.setdefault(shift, {"signal": signal, "files": set()})
        if breaking and "breaking" not in bucket["signal"]:
            bucket["signal"] = signal
        bucket["files"].add(name)

    for status, name in paths:
        low = name.lower()
        leaf = name.rsplit("/", 1)[-1]
        if _AUTH_FILE.search(low):
            add("auth & identity", "auth/identity path touched", name)
        if _API_FILE.search(low):
            if status[:1] == "D":
                add(
                    "public API contract",
                    "breaking: public API surface removed",
                    name,
                    breaking=True,
                )
            else:
                add(
                    "public API contract",
                    "public API contract changed",
                    name,
                )
        if _SCHEMA_FILE.search(low):
            add("data model / schema", "data-model/schema path touched", name)
        if _MAJOR_DEP.search(name):
            if status[:1] == "D":
                add(
                    "dependency upgrades",
                    "breaking: dependency manifest removed",
                    name,
                    breaking=True,
                )
            else:
                add(
                    "dependency upgrades",
                    "dependency manifest changed",
                    name,
                )
        if _CI_FILE.search(low):
            add("build & CI", "build/CI configuration changed", name)
        if _CONFIG_FILE.search(name):
            if status[:1] == "D":
                add(
                    "configuration & secrets",
                    "breaking: configuration removed",
                    name,
                    breaking=True,
                )
            else:
                add(
                    "configuration & secrets",
                    "configuration/secret path changed",
                    name,
                )
        if _CROSS_FILE.search(low):
            add(
                "cross-cutting",
                "logging/telemetry/error path touched",
                name,
            )
        if _PERF_FILE.search(low):
            add("performance", "performance-sensitive path touched", name)
        if _SECURITY_FILE.search(low):
            add("security hardening", "security path touched", name)
        if status[:1] == "M" and "." not in leaf:
            add(
                "submodule pointer bumps",
                "submodule pointer moved",
                name,
            )
        if _TOOLING_FILE.search(low):
            add("tooling / agents", "tooling/agent path changed", name)
    return fired


class _Resolver:
    def __init__(self, config_path, repo):
        self.patterns = []
        if config_path and _modules is not None:
            try:
                self.patterns = _modules.patterns_from_config(config_path)
            except (OSError, ValueError, json.JSONDecodeError):
                self.patterns = []
        self.repo = repo

    def fold(self, files):
        if _modules is None or not self.patterns:
            return ["root"]
        ids = set()
        for name in files:
            ids.add(_modules.module_id(name, self.patterns))
        return sorted(ids) if ids else ["root"]


def _build_changes(commits, paths, classified_units):
    groups = {}
    for index, (_, subject) in enumerate(commits):
        ctype = _conventional_type(subject)
        if ctype is None and classified_units and index < len(classified_units):
            unit = classified_units[index]
            if isinstance(unit, dict):
                ctype = _unit_type(unit)
        if ctype is None:
            ctype = _heuristic_type(paths)
        groups.setdefault(ctype, []).append(subject)

    out = []
    for gtype in GROUP_ORDER:
        if gtype not in groups or not groups[gtype]:
            continue
        subjects = groups[gtype]
        out.append(
            {
                "type": gtype,
                "count": len(subjects),
                "subjects": subjects[:SUBJECT_CAP],
            }
        )
    for gtype in sorted(groups):
        if gtype in GROUP_ORDER:
            continue
        subjects = groups[gtype]
        out.append(
            {
                "type": gtype,
                "count": len(subjects),
                "subjects": subjects[:SUBJECT_CAP],
            }
        )
    return out


def _build_shifts(paths, resolver):
    fired = _shift_signals(paths)
    rows = []
    for shift in SHIFT_ORDER:
        if shift not in fired:
            continue
        bucket = fired[shift]
        rows.append(
            {
                "shift": shift,
                "signal": bucket["signal"],
                "modules": resolver.fold(sorted(bucket["files"])),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(prog="classify-changes.py")
    parser.add_argument("--commits", required=True)
    parser.add_argument("--changed", required=True)
    parser.add_argument("--classified")
    parser.add_argument("--config")
    parser.add_argument("--repo")
    parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args()
    except SystemExit:
        return 1

    commit_lines = _read_lines(args.commits)
    changed_lines = _read_lines(args.changed)
    if commit_lines is None:
        sys.stderr.write(f"unreadable commits: {args.commits}\n")
        return 2
    if changed_lines is None:
        sys.stderr.write(f"unreadable changed-files: {args.changed}\n")
        return 2

    commits = _parse_commits(commit_lines)
    paths = _parse_changed(changed_lines)

    classified_units = None
    if args.classified:
        classified_units = _classified_units(args.classified)
        if classified_units is None:
            sys.stderr.write(
                f"unreadable classified: {args.classified}\n"
            )
            return 2

    if not commits and not paths:
        document = {"changes": {"groups": []}, "shifts": {"rows": []}}
    else:
        resolver = _Resolver(args.config, args.repo)
        document = {
            "changes": {
                "groups": _build_changes(commits, paths, classified_units)
            },
            "shifts": {"rows": _build_shifts(paths, resolver)},
        }

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {out_path} "
        f"groups={len(document['changes']['groups'])} "
        f"shifts={len(document['shifts']['rows'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
