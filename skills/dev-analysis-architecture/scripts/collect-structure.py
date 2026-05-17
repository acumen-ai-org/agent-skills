#!/usr/bin/env python3
"""Static, tool-free module/dependency and ADR inventory for a repo.

Usage: collect-structure.py <repo> <out_dir> [ref]

The no-tool fallback for dev-analysis-architecture: when every external
analyzer runner exits 3 (Node/Docker/.NET/cargo absent), this scans source
text directly with the Python standard library and `git` only — no external
analyzer, no Docker, nothing installed.

It produces one raw JSON in <out_dir> carrying:

  - nodes: one per source file that participates in an import edge, keyed by
    repo-relative path, grouped by top-level package directory.
  - edges: directed source -> target file pairs with `value` = the number of
    import/reference statements from source resolving to target.
  - adrs: every Architecture Decision Record found via the configurable glob
    set, with path, title, and status.
  - stacks: the languages whose import syntax was matched, for the role.

Languages scanned by import/reference syntax: TS/JS (import / require),
Python (import / from), C#/F# (using + .csproj/.fsproj <ProjectReference>),
Rust (mod / use), Go (import). Edges resolve only to files inside the repo;
third-party imports are dropped (an internal-structure inventory, not an SBOM).

With a [ref] every file is read from `git show <ref>:<path>`, so a release
tag can be inventoried without checking it out. Without a ref the tracked
working tree (`git ls-files`) is scanned.

Exit codes:
  0  raw JSON written
  1  bad arguments
  5  repo invalid (not a dir / not a git repo / bad ref)
"""
import json
import pathlib
import re
import subprocess
import sys

RAW_NAME = "architecture-source.raw.json"

ADR_GLOBS = (
    "docs/adr*/**/*.md",
    "docs/adr*/*.md",
    "docs/decisions/**/*.md",
    "docs/decisions/*.md",
    "adr/**/*.md",
    "adr/*.md",
    "**/*-adr-*.md",
)

SOURCE_SUFFIXES = {
    ".ts": "ts",
    ".tsx": "ts",
    ".mts": "ts",
    ".cts": "ts",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".py": "python",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".rs": "rust",
    ".go": "go",
}

PROJECT_SUFFIXES = {".csproj": "csharp", ".fsproj": "fsharp"}

JS_IMPORT = re.compile(
    r"""(?:import\s[^'"]*?from\s*['"]([^'"]+)['"])"""
    r"""|(?:import\s*['"]([^'"]+)['"])"""
    r"""|(?:require\(\s*['"]([^'"]+)['"]\s*\))"""
    r"""|(?:export\s[^'"]*?from\s*['"]([^'"]+)['"])"""
)
PY_IMPORT = re.compile(r"^\s*import\s+([a-zA-Z0-9_.]+)", re.MULTILINE)
PY_FROM = re.compile(
    r"^\s*from\s+(\.*[a-zA-Z0-9_.]*)\s+import\s+([^\n#]+)", re.MULTILINE
)
CS_USING = re.compile(r"^\s*using\s+(?:static\s+)?([A-Za-z_][\w.]*)\s*;", re.MULTILINE)
PROJ_REF = re.compile(r'<ProjectReference\s+Include="([^"]+)"')
RUST_USE = re.compile(r"^\s*(?:pub\s+)?use\s+(?:crate::|self::|super::)?([A-Za-z_][\w:]*)", re.MULTILINE)
RUST_MOD = re.compile(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_]\w*)\s*;", re.MULTILINE)
GO_IMPORT_BLOCK = re.compile(r"import\s*\(([^)]*)\)", re.DOTALL)
GO_IMPORT_SINGLE = re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE)
GO_IMPORT_PATH = re.compile(r'"([^"]+)"')
ADR_STATUS = re.compile(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?status(?:\*\*)?\s*[:=]\s*(.+?)\s*$")
ADR_TITLE = re.compile(r"(?m)^\s*#\s+(.+?)\s*$")


def run_git(repo, args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def is_git_repo(repo):
    result = run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def ref_exists(repo, ref):
    return run_git(repo, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]).returncode == 0


def list_files(repo, ref):
    if ref is None:
        result = run_git(repo, ["ls-files", "-z"])
    else:
        result = run_git(repo, ["ls-tree", "-r", "-z", "--name-only", ref])
    if result.returncode != 0:
        return []
    return [item for item in result.stdout.split("\0") if item]


def read_file(repo, ref, rel_path):
    if ref is None:
        try:
            return (pathlib.Path(repo) / rel_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    result = run_git(repo, ["show", f"{ref}:{rel_path}"])
    if result.returncode != 0:
        return None
    return result.stdout


def group_of(rel_path):
    parts = pathlib.PurePosixPath(rel_path).parts
    return parts[0] if len(parts) > 1 else "."


def js_candidates(target, source_rel):
    base = pathlib.PurePosixPath(source_rel).parent
    resolved = (base / target) if target.startswith(".") else None
    bases = []
    if resolved is not None:
        normalized = pathlib.PurePosixPath(*_normalize(resolved.parts))
        bases.append(str(normalized))
    out = []
    for stem in bases:
        for suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"):
            out.append(stem + suffix)
        for index in ("index.ts", "index.tsx", "index.js", "index.jsx"):
            out.append(f"{stem}/{index}")
    return out


def _normalize(parts):
    stack = []
    for part in parts:
        if part == ".":
            continue
        if part == "..":
            if stack:
                stack.pop()
            continue
        stack.append(part)
    return stack


def py_module_to_paths(module, source_rel, is_relative):
    if is_relative:
        base = pathlib.PurePosixPath(source_rel).parent
        dots = len(module) - len(module.lstrip("."))
        for _ in range(dots - 1):
            base = base.parent
        tail = module.lstrip(".")
        target_parts = list(base.parts) + (tail.split(".") if tail else [])
    else:
        target_parts = module.split(".")
    target_parts = _normalize(target_parts)
    if not target_parts:
        return []
    joined = "/".join(target_parts)
    candidates = [f"{joined}.py", f"{joined}/__init__.py"]
    if len(target_parts) > 1:
        parent = "/".join(target_parts[:-1])
        candidates.append(f"{parent}.py")
        candidates.append(f"{parent}/__init__.py")
    return candidates


def collect_edges(repo, ref, files):
    source_files = {}
    csharp_namespace_index = {}
    for rel in files:
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        if suffix in SOURCE_SUFFIXES:
            source_files[rel] = SOURCE_SUFFIXES[suffix]

    file_set = set(files)
    edge_counts = {}
    stacks = set()

    for rel in files:
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        if suffix in PROJECT_SUFFIXES:
            text = read_file(repo, ref, rel)
            if text is None:
                continue
            stacks.add(PROJECT_SUFFIXES[suffix])
            base = pathlib.PurePosixPath(rel).parent
            for match in PROJ_REF.finditer(text):
                ref_path = match.group(1).replace("\\", "/")
                normalized = pathlib.PurePosixPath(*_normalize((base / ref_path).parts))
                target = str(normalized)
                if target in file_set:
                    _bump(edge_counts, rel, target)

    for rel in files:
        text = read_file(repo, ref, rel)
        if text is None:
            continue
        if "namespace " in text and rel.endswith(".cs"):
            for ns_match in re.finditer(r"namespace\s+([A-Za-z_][\w.]*)", text):
                csharp_namespace_index.setdefault(ns_match.group(1), set()).add(rel)

    for rel, lang in source_files.items():
        text = read_file(repo, ref, rel)
        if text is None:
            continue
        if lang in ("ts", "js"):
            stacks.add("typescript" if lang == "ts" else "javascript")
            for match in JS_IMPORT.finditer(text):
                spec = next((group for group in match.groups() if group), None)
                if not spec or not spec.startswith("."):
                    continue
                for candidate in js_candidates(spec, rel):
                    if candidate in file_set:
                        _bump(edge_counts, rel, candidate)
                        break
        elif lang == "python":
            stacks.add("python")
            for match in PY_IMPORT.finditer(text):
                for candidate in py_module_to_paths(match.group(1), rel, False):
                    if candidate in file_set:
                        _bump(edge_counts, rel, candidate)
                        break
            for match in PY_FROM.finditer(text):
                module = match.group(1)
                is_relative = module.startswith(".")
                modules = []
                for name in re.findall(r"[A-Za-z_]\w*", match.group(2)):
                    if name == "import":
                        continue
                    joined = module if module.endswith(".") else module + "."
                    modules.append(joined + name)
                modules.append(module)
                resolved = False
                for candidate_module in modules:
                    for candidate in py_module_to_paths(candidate_module, rel, is_relative):
                        if candidate in file_set:
                            _bump(edge_counts, rel, candidate)
                            resolved = True
                            break
                    if resolved:
                        break
        elif lang == "csharp":
            stacks.add("csharp")
            for match in CS_USING.finditer(text):
                targets = csharp_namespace_index.get(match.group(1))
                if not targets:
                    continue
                for target in sorted(targets):
                    if target != rel:
                        _bump(edge_counts, rel, target)
                        break
        elif lang == "rust":
            stacks.add("rust")
            base = pathlib.PurePosixPath(rel).parent
            for match in RUST_MOD.finditer(text):
                name = match.group(1)
                for candidate in (f"{base}/{name}.rs", f"{base}/{name}/mod.rs"):
                    if candidate in file_set:
                        _bump(edge_counts, rel, candidate)
                        break
            for match in RUST_USE.finditer(text):
                head = match.group(1).split("::")[0]
                for candidate in (f"{base}/{head}.rs", f"{base}/{head}/mod.rs"):
                    if candidate in file_set:
                        _bump(edge_counts, rel, candidate)
                        break
        elif lang == "go":
            stacks.add("go")
            specs = []
            for block in GO_IMPORT_BLOCK.finditer(text):
                specs.extend(GO_IMPORT_PATH.findall(block.group(1)))
            specs.extend(GO_IMPORT_SINGLE.findall(text))
            for spec in specs:
                tail = spec.split("/")[-1]
                for candidate in files:
                    if candidate.endswith(".go") and pathlib.PurePosixPath(candidate).parent.name == tail:
                        _bump(edge_counts, rel, candidate)
                        break

    nodes = {}
    for (source, target), value in edge_counts.items():
        for member in (source, target):
            if member not in nodes:
                nodes[member] = {
                    "id": member,
                    "label": pathlib.PurePosixPath(member).name,
                    "group": group_of(member),
                }
    edges = [
        {"source": source, "target": target, "value": value}
        for (source, target), value in sorted(edge_counts.items())
    ]
    return list(nodes.values()), edges, sorted(stacks)


def _bump(counts, source, target):
    if source == target:
        return
    key = (source, target)
    counts[key] = counts.get(key, 0) + 1


def _adr_match(rel, glob):
    candidates = {glob}
    if glob.startswith("**/"):
        candidates.add(glob[3:])
    path = pathlib.PurePosixPath(rel)
    return any(path.match(pattern) for pattern in candidates)


def collect_adrs(repo, ref, files):
    seen = set()
    matched = []
    for glob in ADR_GLOBS:
        for rel in files:
            if rel in seen:
                continue
            if not rel.lower().endswith(".md"):
                continue
            if _adr_match(rel, glob):
                seen.add(rel)
                matched.append(rel)
    adrs = []
    for rel in sorted(matched):
        text = read_file(repo, ref, rel)
        title = pathlib.PurePosixPath(rel).stem
        status = "unknown"
        if text is not None:
            title_match = ADR_TITLE.search(text)
            if title_match:
                title = title_match.group(1).strip()
            status_match = ADR_STATUS.search(text)
            if status_match:
                status = status_match.group(1).strip()
        adrs.append({"path": rel, "title": title, "status": status})
    return adrs


def main():
    if len(sys.argv) not in (3, 4):
        sys.stderr.write("usage: collect-structure.py <repo> <out_dir> [ref]\n")
        return 1

    repo = pathlib.Path(sys.argv[1])
    out_dir = pathlib.Path(sys.argv[2])
    ref = sys.argv[3] if len(sys.argv) == 4 else None

    if not repo.is_dir():
        sys.stderr.write(f"repo is not a directory: {repo}\n")
        print("TOOL collect-structure exit=5")
        return 5
    if not is_git_repo(repo):
        sys.stderr.write(f"repo is not a git repository: {repo}\n")
        print("TOOL collect-structure exit=5")
        return 5
    if ref is not None and not ref_exists(repo, ref):
        sys.stderr.write(f"ref does not resolve to a commit: {ref}\n")
        print("TOOL collect-structure exit=5")
        return 5

    files = list_files(repo, ref)
    nodes, edges, stacks = collect_edges(repo, ref, files)
    adrs = collect_adrs(repo, ref, files)

    raw = {
        "kind": "architecture-source",
        "repo": str(repo),
        "ref": ref,
        "stacks": stacks,
        "nodes": nodes,
        "edges": edges,
        "adrs": adrs,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / RAW_NAME
    out_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} nodes={len(nodes)} edges={len(edges)} adrs={len(adrs)}")
    print("TOOL collect-structure exit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
