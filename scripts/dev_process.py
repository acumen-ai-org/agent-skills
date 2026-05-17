#!/usr/bin/env python3
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys

SCHEMA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "skills" / "dev-release-candidate" / "references" / "dev-process.schema.json"
)

DEFAULT = {
    "version": 1,
    "branches": {
        "main": "main",
        "production": "production",
        "releaseCandidate": "release-candidate",
    },
    "scope": {
        "range": "${production}..${main}",
        "productionRef": {"strategy": "branch", "tagPattern": "v*", "commit": None},
        "fallbackOrder": ["branch", "tag", "root"],
        "changedFilesPathspec": [],
    },
    "analysis": [
        {
            "id": "build",
            "title": "Build (sample - replace)",
            "kind": "command",
            "run": "echo 'configure analysis[].run in dev-process.json' && exit 0",
            "report": {"format": "text"},
            "heavy": False,
            "parallelizable": True,
            "blocking": False,
            "advisory": True,
            "timeoutSeconds": 1800,
            "enabled": True,
        }
    ],
    "review": [
        {
            "id": "code-review",
            "title": "Code review (sample - replace)",
            "kind": "skill",
            "run": "agent-skills:review",
            "args": {"range": "${scope.range}"},
            "report": {"format": "markdown"},
            "heavy": True,
            "parallelizable": True,
            "blocking": False,
            "advisory": True,
            "timeoutSeconds": 1800,
            "enabled": False,
        }
    ],
    "reports": {
        "outputDir": ".agents/release-reports",
        "viewerPath": ".agents/release-reports/index.html",
        "persistInRepo": "none",
        "mediaExtensions": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".pdf", ".zip"],
        "persistPath": "release-reports",
        "aggregate": {"kind": "command", "run": None},
        "designDoc": None,
    },
    "releaseNotes": {
        "path": "RELEASE_NOTES.md",
        "changelogPath": "CHANGELOG.md",
        "sources": ["commits", "PRs"],
        "changelogMode": "prepend",
        "commitSubjectFilter": None,
        "generate": {"kind": "command", "run": None},
    },
    "blob": {
        "provider": "none",
        "prefix": "releases/${releaseId}",
    },
    "modules": [],
}

TYPE_NAMES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
    "number": (int, float),
    "null": type(None),
}


def get_schema():
    if not SCHEMA_PATH.exists():
        sys.stderr.write(f"bundled schema missing: {SCHEMA_PATH}\n")
        raise SystemExit(2)
    return json.loads(SCHEMA_PATH.read_text())


def type_ok(value, spec):
    if spec is None:
        return True
    names = spec if isinstance(spec, list) else [spec]
    for name in names:
        expected = TYPE_NAMES[name]
        if name == "integer":
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return True
            continue
        if name == "number" and isinstance(value, bool):
            continue
        if isinstance(value, expected):
            return True
    return False


def resolve_ref(ref, root):
    node = root
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def validate(value, schema, root, path, errors):
    if "$ref" in schema:
        validate(value, resolve_ref(schema["$ref"], root), root, path, errors)
        return

    if "type" in schema and not type_ok(value, schema["type"]):
        errors.append(f"{path or '/'}: expected type {schema['type']}, got {type(value).__name__}")
        return

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path or '/'}: must equal {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path or '/'}: {value!r} not in {schema['enum']}")

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"{path or '/'}: {value!r} does not match /{schema['pattern']}/")

    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            errors.append(f"{path or '/'}: {value} < minimum {schema['minimum']}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path or '/'}: missing required property '{req}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path or '/'}: unexpected property '{key}'")
        for key, sub in value.items():
            if key in props:
                validate(sub, props[key], root, f"{path}/{key}", errors)

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], root, f"{path}/{i}", errors)

    for sub in schema.get("allOf", []):
        validate(value, sub, root, path, errors)

    if "if" in schema:
        probe = []
        validate(value, schema["if"], root, path, probe)
        branch = schema.get("then") if not probe else schema.get("else")
        if branch is not None:
            validate(value, branch, root, path, errors)


def git_short_sha(repo):
    try:
        out = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"


def release_id(repo):
    override = os.environ.get("DEV_RELEASE_ID")
    if override:
        return override
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    return f"{day}-{git_short_sha(repo)}"


def effective_release_candidate_branch(cfg):
    return cfg["branches"]["releaseCandidate"]


def build_tokens(cfg, repo):
    flat = {}

    def walk(pfx, node):
        if isinstance(node, dict):
            for k, v in node.items():
                key = f"{pfx}{k}" if not pfx else f"{pfx}.{k}"
                if isinstance(v, (str, int)) and not isinstance(v, bool):
                    flat[key] = str(v)
                walk(key, v)

    walk("", cfg)
    flat["main"] = cfg["branches"]["main"]
    flat["production"] = cfg["branches"]["production"]
    flat["releaseId"] = release_id(repo)
    flat["releaseCandidateBranch"] = effective_release_candidate_branch(cfg)
    return flat


def substitute(obj, tokens):
    pat = re.compile(r"\$\{([^}]+)\}")

    def one(s):
        for _ in range(6):
            new = pat.sub(lambda m: tokens.get(m.group(1), m.group(0)), s)
            if new == s:
                return new
            s = new
        return s

    if isinstance(obj, str):
        return one(obj)
    if isinstance(obj, list):
        return [substitute(x, tokens) for x in obj]
    if isinstance(obj, dict):
        return {k: substitute(v, tokens) for k, v in obj.items()}
    return obj


def load(config_path):
    return json.loads(pathlib.Path(config_path).read_text())


def do_check(config_path):
    if not pathlib.Path(config_path).exists():
        sys.stderr.write(f"config not found: {config_path}\n")
        return 2
    try:
        cfg = load(config_path)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"{config_path}: invalid JSON: {exc}\n")
        return 2
    schema = get_schema()
    errors = []
    validate(cfg, schema, schema, "", errors)
    if errors:
        for e in errors:
            sys.stderr.write(f"{e}\n")
        return 2
    return 0


def do_init(config_path, repo):
    cfg_file = pathlib.Path(config_path)
    if not cfg_file.exists():
        try:
            cfg_file.write_text(json.dumps(DEFAULT, indent=2) + "\n")
        except OSError as exc:
            sys.stderr.write(f"cannot write {cfg_file}: {exc}\n")
            return 4
        sys.stderr.write(
            f"wrote default {cfg_file}; "
            "edit analysis/review/blob before a real release; review and commit it\n"
        )
        return 0
    return do_check(config_path)


def do_emit(config_path, repo):
    rc = do_check(config_path)
    if rc != 0:
        return rc
    cfg = load(config_path)
    tokens = build_tokens(cfg, repo)
    sys.stdout.write(json.dumps(substitute(cfg, tokens), indent=2) + "\n")
    return 0


def do_schema():
    sys.stdout.write(json.dumps(get_schema(), indent=2) + "\n")
    return 0


def do_value(config_path, repo, what):
    rc = do_check(config_path)
    if rc != 0:
        return rc
    cfg = load(config_path)
    if what == "release-candidate-branch":
        sys.stdout.write(effective_release_candidate_branch(cfg) + "\n")
    elif what == "release-id":
        sys.stdout.write(release_id(repo) + "\n")
    else:
        sys.stderr.write("usage: dev_process.py value <release-candidate-branch|release-id>\n")
        return 1
    return 0


def main():
    modes = {"init", "check", "emit", "schema", "value"}
    if len(sys.argv) < 2 or sys.argv[1] not in modes:
        sys.stderr.write("usage: dev_process.py <init|check|emit|schema|value>\n")
        return 1
    mode = sys.argv[1]
    config_path = os.environ.get("DEV_RELEASE_CONFIG", "./dev-process.json")
    repo = os.environ.get("DEV_RELEASE_REPO", ".")
    if mode == "schema":
        return do_schema()
    if mode == "init":
        return do_init(config_path, repo)
    if mode == "check":
        return do_check(config_path)
    if mode == "value":
        return do_value(config_path, repo, sys.argv[2] if len(sys.argv) > 2 else "")
    return do_emit(config_path, repo)


if __name__ == "__main__":
    raise SystemExit(main())
