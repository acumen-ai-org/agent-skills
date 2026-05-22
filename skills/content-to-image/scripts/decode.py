#!/usr/bin/env python3
"""Decode an image-generation JSON response into a PNG.

Provider-agnostic across the three backends content-to-image renders with:
- OpenAI (gpt-image-1) and Azure Foundry (gpt-image-2): {"data":[{"b64_json":...}]}
- Gemini (gemini-3.1-flash-image-preview): the b64 image lives at
  candidates[].content.parts[].inlineData.data

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


def extract_b64(resp):
    items = resp.get("data")
    if isinstance(items, list) and items and items[0].get("b64_json"):
        return items[0]["b64_json"]
    for candidate in resp.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return inline["data"]
    return None


def main() -> int:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: decode.py <response.json> <out.png>\n")
        return 1

    resp_path = pathlib.Path(sys.argv[1])
    out_path = pathlib.Path(sys.argv[2])

    b64 = extract_b64(json.loads(resp_path.read_text()))
    if b64 is None:
        # Not an exception: a well-formed error response (rate limit, content
        # filter, bad prompt) lands here. The caller keeps response.json and
        # surfaces it rather than writing a corrupt PNG.
        sys.stderr.write(f"image API returned no image; see {resp_path}\n")
        return 2

    out_path.write_bytes(base64.b64decode(b64))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
