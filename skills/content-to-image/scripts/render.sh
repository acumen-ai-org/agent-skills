#!/usr/bin/env bash
# Render a content-to-image brief via gpt-image, on Azure Foundry or OpenAI.
#
# Usage: render.sh <brief.md> <out.json>
#   <brief.md>  final image-generation prompt (prompt-synth output, + theme block if any)
#   <out.json>  where the raw API response is written
#
# Provider: set IMAGE_PROVIDER=foundry|openai. If unset, defaults to openai
# when OPENAI_API_KEY is set and no Foundry endpoint is configured, else
# foundry. Both providers return {"data":[{"b64_json":...}]}, so decode.py is
# provider-agnostic.
#
# Exit: 0 on HTTP 2xx; non-zero on transport failure. The HTTP status is
# printed on stderr-style trailing line ("HTTP <code> time=<s>") so the caller
# can detect a non-200 and skip decoding. The provider selection plus the
# upstream-overload retry/fallback flow live in render-lib.sh, shared with
# text-to-image.sh.
set -euo pipefail

brief_path=${1:?usage: render.sh <brief.md> <out.json>}
out_json=${2:?usage: render.sh <brief.md> <out.json>}

# shellcheck source=render-lib.sh
. "$(dirname "$0")/render-lib.sh"

prompt=$(cat "$brief_path")

render_rc=0
run_render "$prompt" "$out_json" || render_rc=$?
exit "$render_rc"
