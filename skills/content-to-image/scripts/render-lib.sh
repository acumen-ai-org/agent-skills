#!/usr/bin/env bash
# Shared image-generation request flow for content-to-image.
#
# Sourced by render.sh (full pipeline) and text-to-image.sh (one-shot). Holds
# the provider selection plus the overload retry/fallback behavior so neither
# caller duplicates it. The entry point is run_render <prompt> <out.json>: it
# prints "HTTP <code> time=<s>" lines on stdout exactly as render.sh always
# has, surfaces the same stderr messages, and returns (does not exit) the
# status the caller should propagate. render_attempt_log is set to the same
# human-readable per-attempt provider+status list render.sh reports on
# exhaustion, so a one-shot caller can show diagnostics even on success.
set -euo pipefail

render_attempt_log=

run_render() {
  local prompt=$1
  local out_json=$2

  local provider=${IMAGE_PROVIDER:-}
  if [ -z "$provider" ]; then
    if [ -n "${AZURE_FOUNDRY_IMAGE_ENDPOINT:-}" ] || [ -n "${AZURE_OPENAI_ENDPOINT:-}" ]; then
      provider=foundry
    else
      provider=openai
    fi
  fi

  local url auth_header body model base_url endpoint deployment api_version
  local last_curl_rc=0 last_http_status= attempted= retry_provider= delay

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
        endpoint=${AZURE_FOUNDRY_IMAGE_ENDPOINT:-${AZURE_OPENAI_ENDPOINT:-https://example-foundry.services.ai.azure.com}}
        deployment=${AZURE_FOUNDRY_IMAGE_DEPLOYMENT:-${AZURE_OPENAI_DEPLOYMENT:-gpt-image-2}}
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
        return 1
        ;;
    esac
  }

  do_request() {
    build_request "$1" || return 1
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

  do_request "$provider" || return 1
  render_attempt_log="${provider}(HTTP ${last_http_status})"
  if ! is_overload; then
    return "$last_curl_rc"
  fi

  attempted="${provider}(HTTP ${last_http_status})"

  if [ "$provider" = foundry ] && openai_available; then
    do_request openai || return 1
    if ! is_overload; then
      render_attempt_log="${attempted}, openai-fallback(HTTP ${last_http_status})"
      return "$last_curl_rc"
    fi
    attempted="${attempted}, openai-fallback(HTTP ${last_http_status})"
    retry_provider=openai
  else
    retry_provider=$provider
  fi
  render_attempt_log="$attempted"

  for delay in 5 15 30; do
    sleep "$delay"
    do_request "$retry_provider" || return 1
    if ! is_overload; then
      render_attempt_log="${attempted}, ${retry_provider}-retry+${delay}s(HTTP ${last_http_status})"
      return "$last_curl_rc"
    fi
    attempted="${attempted}, ${retry_provider}-retry+${delay}s(HTTP ${last_http_status})"
    render_attempt_log="$attempted"
  done

  echo "render.sh: upstream image provider overloaded; all retries exhausted (providers/attempts tried: ${attempted})" >&2
  return 2
}
