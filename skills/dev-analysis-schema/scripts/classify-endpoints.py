#!/usr/bin/env python3
import json
import os
import pathlib
import re
import sys

USAGE = "usage: classify-endpoints.py <openapi.json> <out_dir>\n"

PRIVATE_PATH_PATTERNS = [
    re.compile(pattern)
    for pattern in os.environ.get(
        "SCHEMA_PRIVATE_PATH_PATTERNS",
        r"^/internal,^/admin,^/_,^/debug,/internal/",
    ).split(",")
    if pattern
]
PUBLIC_PATH_PATTERNS = [
    re.compile(pattern)
    for pattern in os.environ.get("SCHEMA_PUBLIC_PATH_PATTERNS", "").split(",")
    if pattern
]
INTERNAL_EXTENSION = os.environ.get("SCHEMA_INTERNAL_EXTENSION", "x-internal")
PRIVATE_SECURITY_SCHEMES = {
    name.strip()
    for name in os.environ.get("SCHEMA_PRIVATE_SECURITY_SCHEMES", "").split(",")
    if name.strip()
}

HTTP_METHODS = {
    "get",
    "put",
    "post",
    "delete",
    "options",
    "head",
    "patch",
    "trace",
}


def truthy_internal(node):
    if not isinstance(node, dict):
        return False
    flag = node.get(INTERNAL_EXTENSION)
    return flag is True or flag == "true"


def operation_is_private(path, method, operation, document):
    if PUBLIC_PATH_PATTERNS and any(
        pattern.search(path) for pattern in PUBLIC_PATH_PATTERNS
    ):
        if not truthy_internal(operation):
            return False, "public-path-allowlist"
    if truthy_internal(operation):
        return True, "x-internal-operation"
    if any(pattern.search(path) for pattern in PRIVATE_PATH_PATTERNS):
        return True, "private-path-pattern"
    security = operation.get("security")
    if security is None:
        security = document.get("security")
    if isinstance(security, list):
        for requirement in security:
            if isinstance(requirement, dict):
                for scheme_name in requirement:
                    if scheme_name in PRIVATE_SECURITY_SCHEMES:
                        return True, f"private-security-scheme:{scheme_name}"
    return False, "default-public"


def split_document(document):
    public = json.loads(json.dumps(document))
    private = json.loads(json.dumps(document))
    public_paths = {}
    private_paths = {}
    classifications = []

    paths = document.get("paths")
    if not isinstance(paths, dict):
        return public, private, classifications

    path_internal = {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        whole_path_internal = truthy_internal(path_item)
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            is_private, reason = operation_is_private(
                path, method, operation, document
            )
            if whole_path_internal:
                is_private, reason = True, "x-internal-path"
            bucket = private_paths if is_private else public_paths
            bucket.setdefault(path, {})
            shared = paths[path]
            for shared_key, shared_value in shared.items():
                if shared_key.lower() in HTTP_METHODS:
                    continue
                bucket[path].setdefault(shared_key, shared_value)
            bucket[path][method] = operation
            classifications.append(
                {
                    "path": path,
                    "method": method.lower(),
                    "visibility": "private" if is_private else "public",
                    "reason": reason,
                }
            )
        path_internal[path] = whole_path_internal

    public["paths"] = public_paths
    private["paths"] = private_paths
    return public, private, classifications


def main():
    if len(sys.argv) != 3:
        sys.stderr.write(USAGE)
        return 1

    schema_path = pathlib.Path(sys.argv[1])
    out_dir = pathlib.Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        document = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        sys.stderr.write(f"unreadable / invalid OpenAPI JSON: {error}\n")
        return 2

    public, private, classifications = split_document(document)

    stem = schema_path.stem
    (out_dir / f"{stem}.public.json").write_text(
        json.dumps(public, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / f"{stem}.private.json").write_text(
        json.dumps(private, indent=2, sort_keys=True), encoding="utf-8"
    )
    (out_dir / f"{stem}.classification.json").write_text(
        json.dumps(classifications, indent=2, sort_keys=True), encoding="utf-8"
    )

    public_count = sum(1 for c in classifications if c["visibility"] == "public")
    private_count = len(classifications) - public_count
    print(
        f"CLASSIFY {stem} public={public_count} private={private_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
