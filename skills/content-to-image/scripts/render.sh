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
# can detect a non-200 and skip decoding.
set -euo pipefail

brief_path=${1:?usage: render.sh <brief.md> <out.json>}
out_json=${2:?usage: render.sh <brief.md> <out.json>}

provider=${IMAGE_PROVIDER:-}
if [ -z "$provider" ]; then
  if [ -n "${OPENAI_API_KEY:-}" ] && [ -z "${AZURE_FOUNDRY_IMAGE_ENDPOINT:-}" ]; then
    provider=openai
  else
    provider=foundry
  fi
fi

prompt=$(cat "$brief_path")

openai_available() {
  [ -n "${OPENAI_API_KEY:-}" ]
}

build_request() {
  case "$1" in
    openai)
      model=${OPENAI_IMAGE_MODEL:-gpt-image-1}
      base_url=${OPENAI_BASE_URL:-https://api.openai.com/v1}
      : "${OPENAI_API_KEY:?IMAGE_PROVIDER=openai requires OPENAI_API_KEY}"
      url="${base_url}/images/generations"
      auth_header="Authorization: Bearer ${OPENAI_API_KEY}"
      # OpenAI takes the model in the body; gpt-image-1 always returns b64_json
      # (no response_format — passing it errors).
      body=$(MODEL="$model" python3 -c "import json,os,sys; print(json.dumps({'model':os.environ['MODEL'],'prompt':sys.stdin.read(),'size':'1536x1024','n':1,'quality':'low'}))" <<<"$prompt")
      ;;
    foundry)
      # Defaults are placeholders; override via environment for a real deployment.
      endpoint=${AZURE_FOUNDRY_IMAGE_ENDPOINT:-https://example-foundry.services.ai.azure.com}
      deployment=${AZURE_FOUNDRY_IMAGE_DEPLOYMENT:-gpt-image-2}
      # 2025-04-01-preview is the version gpt-image-2 image generation requires;
      # an older version returns HTTP 000 (timeout) on this endpoint.
      api_version=${AZURE_FOUNDRY_IMAGE_API_VERSION:-2025-04-01-preview}
      url="${endpoint}/openai/deployments/${deployment}/images/generations?api-version=${api_version}"
      # Foundry puts the model in the URL path (deployment), not the body.
      body=$(python3 -c "import json,sys; print(json.dumps({'prompt':sys.stdin.read(),'size':'1536x1024','n':1,'quality':'low'}))" <<<"$prompt")
      if [ -n "${AZURE_OPENAI_APIKEY:-}" ]; then
        auth_header="api-key: ${AZURE_OPENAI_APIKEY}"
      else
        # Fall back to an Azure AD token scoped to Cognitive Services.
        auth_header="Authorization: Bearer $(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)"
      fi
      ;;
    *)
      echo "unknown IMAGE_PROVIDER='$1' (expected foundry|openai)" >&2
      exit 1
      ;;
  esac
}

last_curl_rc=0
last_http_status=

do_request() {
  build_request "$1"
  local wline
  set +e
  # --max-time 240: image generation regularly takes 60-180s; 240 leaves margin
  # without hanging the pipeline indefinitely.
  wline=$(curl -sS --max-time 240 -X POST \
    "$url" \
    -H "$auth_header" -H "Content-Type: application/json" \
    -d "$body" -o "$out_json" -w "HTTP %{http_code} time=%{time_total}\n")
  last_curl_rc=$?
  set -e
  printf '%s\n' "$wline"
  last_http_status=$(printf '%s' "$wline" | sed -n 's/^HTTP \([0-9]\{1,\}\) .*/\1/p')
}

is_overload() {
  if [ "$last_curl_rc" -ne 0 ]; then
    return 1
  fi
  case "$last_http_status" in
    429|503) return 0 ;;
  esac
  if [ -f "$out_json" ] && grep -qiE 'engineoverloaded|overloaded|currently overloaded|capacity' "$out_json"; then
    return 0
  fi
  return 1
}

do_request "$provider"
if ! is_overload; then
  exit "$last_curl_rc"
fi

attempted="${provider}(HTTP ${last_http_status})"

if [ "$provider" = foundry ] && openai_available; then
  do_request openai
  if ! is_overload; then
    exit "$last_curl_rc"
  fi
  attempted="${attempted}, openai-fallback(HTTP ${last_http_status})"
  retry_provider=openai
else
  retry_provider=$provider
fi

overload_backoff_seconds="5 15 30"
for delay in $overload_backoff_seconds; do
  sleep "$delay"
  do_request "$retry_provider"
  if ! is_overload; then
    exit "$last_curl_rc"
  fi
  attempted="${attempted}, ${retry_provider}-retry+${delay}s(HTTP ${last_http_status})"
done

echo "render.sh: upstream image provider overloaded; all retries exhausted (providers/attempts tried: ${attempted})" >&2
exit 2
