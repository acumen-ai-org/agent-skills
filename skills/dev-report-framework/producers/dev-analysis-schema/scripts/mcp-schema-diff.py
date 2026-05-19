#!/usr/bin/env python3
import json
import pathlib
import sys

USAGE = "usage: mcp-schema-diff.py <base_dir> <revision_dir> <out_raw>\n"


def load_definitions(side_dir):
    definitions = {}
    side_dir = pathlib.Path(side_dir)
    if not side_dir.is_dir():
        return definitions
    for path in sorted(side_dir.glob("*")):
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in iter_named_schemas(document):
            definitions[entry[0]] = entry[1]
    return definitions


def iter_named_schemas(document):
    if isinstance(document, dict):
        for collection_key in ("tools", "resources"):
            collection = document.get(collection_key)
            if isinstance(collection, list):
                for item in collection:
                    if isinstance(item, dict) and isinstance(
                        item.get("name"), str
                    ):
                        schema = (
                            item.get("inputSchema")
                            or item.get("input_schema")
                            or item.get("schema")
                            or {}
                        )
                        yield (
                            f"{collection_key}:{item['name']}",
                            schema,
                        )
            elif isinstance(collection, dict):
                for name, schema in collection.items():
                    yield (f"{collection_key}:{name}", schema)
        if "name" in document and (
            "inputSchema" in document
            or "input_schema" in document
            or "schema" in document
        ):
            schema = (
                document.get("inputSchema")
                or document.get("input_schema")
                or document.get("schema")
                or {}
            )
            yield (str(document["name"]), schema)


def required_set(schema):
    required = schema.get("required") if isinstance(schema, dict) else None
    return set(required) if isinstance(required, list) else set()


def properties(schema):
    props = schema.get("properties") if isinstance(schema, dict) else None
    return props if isinstance(props, dict) else {}


def diff_schema(name, base_schema, revision_schema):
    changes = []
    base_required = required_set(base_schema)
    revision_required = required_set(revision_schema)
    base_props = properties(base_schema)
    revision_props = properties(revision_schema)

    for new_required in sorted(revision_required - base_required):
        changes.append(
            {
                "schema": name,
                "criticality": "BREAKING",
                "kind": "required-property-added",
                "detail": new_required,
            }
        )
    for removed_required in sorted(base_required - revision_required):
        changes.append(
            {
                "schema": name,
                "criticality": "DANGEROUS",
                "kind": "required-property-relaxed",
                "detail": removed_required,
            }
        )
    for removed_prop in sorted(set(base_props) - set(revision_props)):
        criticality = (
            "BREAKING" if removed_prop in base_required else "DANGEROUS"
        )
        changes.append(
            {
                "schema": name,
                "criticality": criticality,
                "kind": "property-removed",
                "detail": removed_prop,
            }
        )
    for added_prop in sorted(set(revision_props) - set(base_props)):
        criticality = (
            "BREAKING" if added_prop in revision_required else "SAFE"
        )
        changes.append(
            {
                "schema": name,
                "criticality": criticality,
                "kind": "property-added",
                "detail": added_prop,
            }
        )
    for shared_prop in sorted(set(base_props) & set(revision_props)):
        base_type = (
            base_props[shared_prop].get("type")
            if isinstance(base_props[shared_prop], dict)
            else None
        )
        revision_type = (
            revision_props[shared_prop].get("type")
            if isinstance(revision_props[shared_prop], dict)
            else None
        )
        if base_type != revision_type:
            changes.append(
                {
                    "schema": name,
                    "criticality": "BREAKING",
                    "kind": "property-type-changed",
                    "detail": f"{shared_prop}: {base_type} -> {revision_type}",
                }
            )
    return changes


def main():
    if len(sys.argv) != 4:
        sys.stderr.write(USAGE)
        return 1

    base_definitions = load_definitions(sys.argv[1])
    revision_definitions = load_definitions(sys.argv[2])
    out_raw = pathlib.Path(sys.argv[3])

    changes = []
    for removed in sorted(set(base_definitions) - set(revision_definitions)):
        changes.append(
            {
                "schema": removed,
                "criticality": "BREAKING",
                "kind": "schema-removed",
                "detail": removed,
            }
        )
    for added in sorted(set(revision_definitions) - set(base_definitions)):
        changes.append(
            {
                "schema": added,
                "criticality": "SAFE",
                "kind": "schema-added",
                "detail": added,
            }
        )
    for shared in sorted(set(base_definitions) & set(revision_definitions)):
        changes.extend(
            diff_schema(
                shared,
                base_definitions[shared],
                revision_definitions[shared],
            )
        )

    out_raw.parent.mkdir(parents=True, exist_ok=True)
    out_raw.write_text(
        json.dumps({"changes": changes}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    breaking = sum(1 for c in changes if c["criticality"] == "BREAKING")
    print(f"TOOL mcp-schema-diff exit=0 changes={len(changes)} breaking={breaking}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
