#!/usr/bin/env python3
"""Resolve repo paths to module ids and list a repo's module set.

A module id classifies a repo-relative forward-slash path under a configured
set of folder patterns. A literal pattern ``X`` claims paths whose first
segment is ``X`` (module id ``X``). A glob pattern ``P/*`` claims paths under
``P/`` (module id ``P/<next segment under P>``). The longest matching pattern
prefix wins. Anything not claimed resolves to ``root``.
"""
import argparse
import json
import os
import sys


def parse_patterns(text):
    out = []
    for raw in text.split(","):
        item = raw.strip()
        if item:
            out.append(item)
    return out


def patterns_from_config(config_path):
    with open(config_path, encoding="utf-8") as handle:
        cfg = json.load(handle)
    value = cfg.get("modules", [])
    if not isinstance(value, list):
        raise ValueError("config 'modules' is not an array")
    return [str(x) for x in value]


def normalize(path):
    return path.replace("\\", "/").strip("/")


def sort_patterns(patterns):
    def prefix(pattern):
        if pattern.endswith("/*"):
            return pattern[:-2]
        return pattern

    return sorted(set(patterns), key=lambda p: (-len(prefix(p)), p))


def module_id(path, patterns):
    norm = normalize(path)
    if not norm:
        return "root"
    segments = norm.split("/")
    for pattern in sort_patterns(patterns):
        if pattern.endswith("/*"):
            prefix = pattern[:-2].strip("/")
            if not prefix:
                continue
            prefix_segments = prefix.split("/")
            if segments[: len(prefix_segments)] == prefix_segments:
                if len(segments) >= len(prefix_segments) + 1:
                    return prefix + "/" + segments[len(prefix_segments)]
        else:
            literal = pattern.strip("/")
            if not literal:
                continue
            literal_segments = literal.split("/")
            if segments[: len(literal_segments)] == literal_segments:
                return literal
    return "root"


def module_set(patterns, repo):
    found = {"root"}
    for pattern in patterns:
        if pattern.endswith("/*"):
            prefix = pattern[:-2].strip("/")
            if not prefix:
                continue
            base = os.path.join(repo, *prefix.split("/"))
            if os.path.isdir(base):
                for entry in os.listdir(base):
                    if os.path.isdir(os.path.join(base, entry)):
                        found.add(prefix + "/" + entry)
        else:
            literal = pattern.strip("/")
            if not literal:
                continue
            if os.path.isdir(os.path.join(repo, *literal.split("/"))):
                found.add(literal)
    rest = sorted(m for m in found if m != "root")
    return ["root"] + rest


def resolve_patterns(args):
    if args.patterns is not None:
        return parse_patterns(args.patterns)
    if args.config is not None:
        return patterns_from_config(args.config)
    return []


def main():
    parser = argparse.ArgumentParser(prog="modules.py", add_help=True)
    sub = parser.add_subparsers(dest="command")

    p_id = sub.add_parser("id")
    p_id.add_argument("path")
    p_id.add_argument("--patterns")
    p_id.add_argument("--config")

    p_list = sub.add_parser("list")
    p_list.add_argument("--patterns")
    p_list.add_argument("--config")
    p_list.add_argument("--repo")

    try:
        args = parser.parse_args()
    except SystemExit:
        return 1

    if args.command is None:
        sys.stderr.write("usage: modules.py <id|list> ...\n")
        return 1

    try:
        patterns = resolve_patterns(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"cannot read patterns: {exc}\n")
        return 1

    if args.command == "id":
        sys.stdout.write(module_id(args.path, patterns) + "\n")
        return 0

    repo = args.repo if args.repo is not None else "."
    if not os.path.isdir(repo):
        sys.stderr.write(f"--repo is not a directory: {repo}\n")
        return 5
    for module in module_set(patterns, repo):
        sys.stdout.write(module + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
