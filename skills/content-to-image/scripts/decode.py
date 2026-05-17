#!/usr/bin/env python3
"""Decode a gpt-image JSON response into a PNG.

Provider-agnostic: Azure Foundry (gpt-image-2) and OpenAI (gpt-image-1) both
return {"data":[{"b64_json":...}]}, so this handles either unchanged.

Usage: decode.py <response.json> <out.png>

Exit codes:
  0  PNG written
  1  bad arguments
  2  API returned no image (response kept for diagnosis)
"""
import base64
import json
import pathlib
import sys


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: decode.py <response.json> <out.png>\n")
        return 1

    resp_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])

    data = json.loads(resp_path.read_text())
    if "data" not in data or not data["data"] or "b64_json" not in data["data"][0]:
        # Not an exception: a well-formed error response (rate limit, content
        # filter, bad prompt) lands here. The caller keeps response.json and
        # surfaces it rather than writing a corrupt PNG.
        sys.stderr.write(f"image API returned no image; see {resp_path}\n")
        return 2

    out_path.write_bytes(base64.b64decode(data["data"][0]["b64_json"]))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
