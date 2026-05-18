#!/usr/bin/env bash
# One-shot text -> image, bypassing the 3-step content-to-image pipeline.
#
# Usage: text-to-image.sh <text|-> <out-image-path>
#   <text>             short text to illustrate; "-" or omitted reads stdin
#   <out-image-path>    where the image is written (PNG on success)
#
# Builds a minimal image prompt directly from the given text (no
# extract/art-direct/prompt-synth) and reuses render-lib.sh's provider call
# plus the upstream-overload retry/fallback flow. On success it decodes the
# real generated image to the output path and reports the winning provider.
#
# Guaranteed artifact: if generation ultimately fails (all providers + 5/15/30s
# retries exhausted, auth, or any other hard failure) it still writes a valid
# image to the output path — a locally generated diagnostic SVG containing the
# headline "Failed to generate image" plus every attempt's provider and HTTP
# status / error. Exit 0 whenever any image (real or fallback) was written;
# non-zero only on bad usage.
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: text-to-image.sh <text|-> <out-image-path>" >&2
  exit 64
fi

if [ "$#" -eq 1 ]; then
  out_image=$1
  source_text=$(cat)
elif [ "$1" = "-" ]; then
  out_image=$2
  source_text=$(cat)
else
  source_text=$1
  out_image=$2
fi

if [ -z "${out_image:-}" ]; then
  echo "usage: text-to-image.sh <text|-> <out-image-path>" >&2
  exit 64
fi

if [ -z "${source_text//[[:space:]]/}" ]; then
  echo "text-to-image.sh: empty input text" >&2
  exit 64
fi

prompt="3:2 landscape clean explanatory illustration, deep primary blue (#1E6FFF) on a midnight-to-indigo gradient, frosted-glass cards, crisp legible labels, no logos, illustrating: ${source_text}"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

response_json="$work_dir/response.json"
attempt_log_file="$work_dir/attempt.log"
render_stderr_file="$work_dir/render.stderr"

render_rc=0
(
  . "$script_dir/render-lib.sh"
  inner_rc=0
  run_render "$prompt" "$response_json" || inner_rc=$?
  printf '%s' "$render_attempt_log" >"$attempt_log_file"
  exit "$inner_rc"
) 2>"$render_stderr_file" || render_rc=$?

attempt_log=
[ -f "$attempt_log_file" ] && attempt_log=$(cat "$attempt_log_file")
render_stderr=
[ -f "$render_stderr_file" ] && render_stderr=$(cat "$render_stderr_file")

if [ -n "$render_stderr" ]; then
  printf '%s\n' "$render_stderr" >&2
fi

decode_rc=0
if [ "$render_rc" -eq 0 ]; then
  python3 "$script_dir/decode.py" "$response_json" "$out_image" || decode_rc=$?
fi

if [ "$render_rc" -eq 0 ] && [ "$decode_rc" -eq 0 ]; then
  provider_succeeded=${attempt_log%%(*}
  echo "text-to-image.sh: REAL image written via ${provider_succeeded:-unknown} -> $out_image" >&2
  exit 0
fi

if [ "$render_rc" -ne 0 ]; then
  failure_reason="image generation failed (render rc ${render_rc})"
elif [ "$decode_rc" -eq 2 ]; then
  failure_reason="provider returned no image (decode rc 2)"
else
  failure_reason="image generation failed (decode rc ${decode_rc})"
fi

attempts=()
if [ -n "$attempt_log" ]; then
  old_ifs=$IFS
  IFS=','
  for attempt in $attempt_log; do
    trimmed=${attempt#"${attempt%%[![:space:]]*}"}
    attempt_label=${trimmed%%(*}
    attempt_status=${trimmed#*(}
    attempt_status=${attempt_status%)}
    attempts+=("${attempt_label}: ${attempt_status}")
  done
  IFS=$old_ifs
fi
if [ "${#attempts[@]}" -eq 0 ]; then
  if [ -n "$render_stderr" ]; then
    attempts=("$render_stderr")
  else
    attempts=("no provider responded")
  fi
fi

python3 "$script_dir/fallback_svg.py" "$out_image" "$failure_reason" "${attempts[@]}"

echo "text-to-image.sh: FALLBACK image written -> $out_image" >&2
echo "text-to-image.sh: reason: $failure_reason" >&2
echo "text-to-image.sh: attempts:" >&2
for attempt in "${attempts[@]}"; do
  echo "text-to-image.sh:   - $attempt" >&2
done
exit 0
