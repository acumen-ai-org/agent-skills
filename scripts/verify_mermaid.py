#!/usr/bin/env python3
"""Verify mermaid diagrams: a stdlib structural lint plus an optional deep parse.

Usage:
  verify_mermaid.py text -            lint one diagram read from stdin
  verify_mermaid.py text <file>       lint one diagram read from <file>
  verify_mermaid.py fragments <dir>   lint every mermaid section in <dir>/*.json

Layer 1 (always on, Python stdlib, no network, no JS) structurally lints the
diagram source. Layer 2 (optional) renders each diagram with mermaid-cli when
mmdc is resolvable on PATH, via npx, or via the official Docker image; a
non-zero render is a hard failure. When no mmdc is resolvable Layer 2 is
skipped and the Layer 1 result stands.

Exit codes:
  0  every diagram passed
  1  bad arguments / usage
  2  unparseable input (unreadable file, invalid JSON, not a directory)
  4  one or more diagrams failed lint or deep parse
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

DIAGRAM_HEADERS = (
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram-v2",
    "stateDiagram",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "C4Context",
    "C4Container",
    "C4Component",
)
DIRECTED_HEADERS = ("flowchart", "graph")
DIRECTIONS = ("TD", "TB", "LR", "RL", "BT")
RESERVED_IDS = ("end", "graph", "subgraph", "class", "click", "style", "linkStyle")
BRACKET_PAIRS = (("[", "]"), ("(", ")"), ("{", "}"))
ARROW_TOKENS = (
    "-->",
    "---",
    "-.->",
    "-.-",
    "==>",
    "===",
    "--x",
    "--o",
    "<-->",
    "x--x",
    "o--o",
    "->>",
    "-->>",
    "--)",
    "--",
    "..>",
    "..",
    ":",
    "==",
)
ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def strip_comments(line):
    cut = line.find("%%")
    if cut != -1:
        return line[:cut]
    return line


def non_empty_lines(source):
    out = []
    for raw in source.splitlines():
        line = raw.strip()
        if line:
            out.append(line)
    return out


def header_of(line):
    token = line.split()[0] if line.split() else line
    for header in DIAGRAM_HEADERS:
        if token == header or line == header or line.startswith(header + " "):
            return header
    return None


def check_header(lines):
    errors = []
    if not lines:
        errors.append("empty diagram")
        return errors, None
    first = lines[0]
    header = header_of(first)
    if header is None:
        errors.append("first line is not a known diagram header")
        return errors, None
    if header in DIRECTED_HEADERS:
        rest = first[len(header):].strip()
        direction = rest.split()[0].rstrip(";") if rest else ""
        if direction not in DIRECTIONS:
            errors.append(
                "missing direction token (one of " + "|".join(DIRECTIONS) + ")"
            )
    if len(lines) < 2:
        errors.append("no content after the header")
    return errors, header


def check_fences(source):
    if "```" in source:
        return ["stray ``` fence in diagram body"]
    return []


def check_brackets(source):
    errors = []
    for opener, closer in BRACKET_PAIRS:
        if source.count(opener) != source.count(closer):
            errors.append("unbalanced '" + opener + "' / '" + closer + "'")
    if source.count('"') % 2 != 0:
        errors.append('unbalanced \'"\'')
    return errors


def check_subgraphs(lines):
    depth = 0
    for line in lines:
        body = strip_comments(line).strip()
        tokens = body.split()
        if tokens and tokens[0] == "subgraph":
            depth += 1
        elif body == "end" or (tokens and tokens[0] == "end" and len(tokens) == 1):
            depth -= 1
            if depth < 0:
                return ["unbalanced subgraph / end"]
    if depth != 0:
        return ["unbalanced subgraph / end"]
    return []


def split_edge_endpoints(segment):
    work = segment
    for opener, closer in BRACKET_PAIRS:
        result = []
        skip = 0
        for char in work:
            if char == opener:
                skip += 1
                continue
            if char == closer and skip > 0:
                skip -= 1
                continue
            if skip == 0:
                result.append(char)
        work = "".join(result)
    cut = work.find('"')
    if cut != -1:
        end = work.find('"', cut + 1)
        if end != -1:
            work = work[:cut] + work[end + 1:]
    cut = work.find("|")
    if cut != -1:
        end = work.find("|", cut + 1)
        if end != -1:
            work = work[:cut] + work[end + 1:]
    return work.strip()


def base_id(token):
    out = token.strip()
    for opener, _ in BRACKET_PAIRS:
        cut = out.find(opener)
        if cut != -1:
            out = out[:cut]
    return out.strip().rstrip(";").strip()


def check_flow_nodes(lines, header):
    if header not in DIRECTED_HEADERS:
        return []
    errors = []
    for line in lines[1:]:
        body = strip_comments(line).strip().rstrip(";")
        if not body:
            continue
        tokens = body.split()
        if tokens and tokens[0] in (
            "subgraph",
            "end",
            "style",
            "linkStyle",
            "classDef",
            "class",
            "click",
            "direction",
        ):
            continue
        arrow = None
        for candidate in ("-->", "---", "-.->", "-.-", "==>", "===", "--x", "--o", "--"):
            if candidate in body:
                arrow = candidate
                break
        if arrow is None:
            ident = base_id(body)
            if ident and all(ch in ID_CHARS for ch in ident) and ident in RESERVED_IDS:
                errors.append("reserved word '" + ident + "' used as a bare node id")
            continue
        left = base_id(split_edge_endpoints(body.split(arrow, 1)[0]))
        right_seg = body.split(arrow, 1)[1]
        right = base_id(split_edge_endpoints(right_seg))
        for ident in (left, right):
            if not ident:
                errors.append("edge endpoint missing around '" + arrow + "'")
                continue
            if all(ch in ID_CHARS for ch in ident) and ident in RESERVED_IDS:
                errors.append("reserved word '" + ident + "' used as a bare node id")
            if not all(ch in ID_CHARS for ch in ident):
                errors.append("node id '" + ident + "' has invalid characters")
    return errors


def lint_diagram(source):
    if not isinstance(source, str) or source.strip() == "":
        return ["empty diagram"]
    lines = non_empty_lines(source)
    errors = []
    errors.extend(check_fences(source))
    header_errors, header = check_header(lines)
    errors.extend(header_errors)
    errors.extend(check_brackets(source))
    errors.extend(check_subgraphs(lines))
    if header is not None:
        errors.extend(check_flow_nodes(lines, header))
    return errors


def resolve_mmdc():
    if shutil.which("mmdc"):
        return ["mmdc"]
    if shutil.which("npx"):
        return ["npx", "--yes", "@mermaid-js/mermaid-cli"]
    if shutil.which("docker"):
        return [
            "docker",
            "run",
            "--rm",
            "-i",
            "minlag/mermaid-cli",
        ]
    return None


def deep_parse(source, runner):
    in_handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix="vm-", suffix=".mmd", delete=False
    )
    with in_handle:
        in_handle.write(source)
    in_path = pathlib.Path(in_handle.name)
    out_path = in_path.with_suffix(".svg")
    try:
        result = subprocess.run(
            runner + ["-i", str(in_path), "-o", str(out_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return result.stderr.strip() or "mmdc exited non-zero"
        return None
    except (OSError, subprocess.SubprocessError) as error:
        return "mmdc invocation failed: " + str(error)
    finally:
        in_path.unlink(missing_ok=True)
        out_path.unlink(missing_ok=True)


def iter_fragment_diagrams(fragments_dir):
    paths = sorted(fragments_dir.glob("*.json"))
    items = []
    read_errors = []
    for path in paths:
        try:
            fragment = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            read_errors.append(path.name + ": unreadable / invalid JSON: " + str(error))
            continue
        if not isinstance(fragment, dict):
            continue
        body = fragment.get("body")
        if not isinstance(body, list):
            continue
        for index, section in enumerate(body):
            if isinstance(section, dict) and section.get("type") == "mermaid":
                items.append((path.name, index, section.get("diagram")))
    return items, read_errors


def run_text(target):
    if target == "-":
        source = sys.stdin.read()
    else:
        path = pathlib.Path(target)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:
            sys.stderr.write("cannot read " + target + ": " + str(error) + "\n")
            return 2
    errors = lint_diagram(source)
    if errors:
        for message in errors:
            sys.stderr.write("text#body[0]: " + message + "\n")
        return 4
    runner = resolve_mmdc()
    if runner is None:
        sys.stderr.write("skipped: mmdc not resolvable; Layer 1 only\n")
        print("OK 1 diagram linted")
        return 0
    failure = deep_parse(source, runner)
    if failure:
        sys.stderr.write("text#body[0]: " + failure + "\n")
        return 4
    print("OK 1 diagram linted and parsed")
    return 0


def run_fragments(target):
    fragments_dir = pathlib.Path(target)
    if not fragments_dir.is_dir():
        sys.stderr.write("not a directory: " + target + "\n")
        return 2
    items, read_errors = iter_fragment_diagrams(fragments_dir)
    for message in read_errors:
        sys.stderr.write(message + "\n")
    failures = []
    for name, index, diagram in items:
        errors = lint_diagram(diagram)
        for message in errors:
            failures.append(name + "#body[" + str(index) + "]: " + message)
    if read_errors or failures:
        for message in failures:
            sys.stderr.write(message + "\n")
        sys.stderr.write(
            "FAIL " + str(len(failures) + len(read_errors)) + " mermaid issue(s)\n"
        )
        return 4
    runner = resolve_mmdc()
    if runner is None:
        sys.stderr.write("skipped: mmdc not resolvable; Layer 1 only\n")
        print("OK " + str(len(items)) + " diagram(s) linted")
        return 0
    deep_failures = []
    for name, index, diagram in items:
        failure = deep_parse(diagram, runner)
        if failure:
            deep_failures.append(name + "#body[" + str(index) + "]: " + failure)
    if deep_failures:
        for message in deep_failures:
            sys.stderr.write(message + "\n")
        sys.stderr.write("FAIL " + str(len(deep_failures)) + " mermaid issue(s)\n")
        return 4
    print("OK " + str(len(items)) + " diagram(s) linted and parsed")
    return 0


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(
            "usage: verify_mermaid.py text -|<file> | fragments <dir>\n"
        )
        return 1
    command, target = argv[1], argv[2]
    if command == "text":
        return run_text(target)
    if command == "fragments":
        return run_fragments(target)
    sys.stderr.write("usage: verify_mermaid.py text -|<file> | fragments <dir>\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
