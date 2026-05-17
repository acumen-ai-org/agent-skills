#!/usr/bin/env bash
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=${DRP_REPO:-.}
export DRP_REPO="$repo"
export DRP_CONFIG=${DRP_CONFIG:-$repo/dev-process.json}
cfg=$(python3 "$here/dev_process.py" emit) || { echo "dev-process: config invalid" >&2; exit 2; }
get() { printf '%s' "$cfg" | python3 -c 'import json,sys
d=json.load(sys.stdin)
for p in sys.argv[1].split("."):
    d = d[int(p)] if p.lstrip("-").isdigit() else d[p]
print("\n".join(str(x) for x in d) if isinstance(d,list) else ("" if d is None else d))' "$1"; }

release_candidate=$(python3 "$here/dev_process.py" value release-candidate-branch)
release_id=$(python3 "$here/dev_process.py" value release-id)
out_dir=$(get reports.outputDir)
persist=$(get reports.persistInRepo)
persist_path=$(get reports.persistPath)
provider=$(get blob.provider)
prefix=$(get blob.prefix)
src="$repo/$out_dir"

cur=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
if [ "$cur" != "$release_candidate" ]; then
  echo "on '$cur'; checkout the release candidate branch '$release_candidate' before finalizing" >&2
  exit 2
fi

if [ ! -d "$src" ] || [ -z "$(find "$src" -type f 2>/dev/null)" ]; then
  echo "no reports at $out_dir; nothing to finalize"
  exit 0
fi

is_media() {
  local f=$1
  while IFS= read -r ext; do
    [ -z "$ext" ] && continue
    case "$f" in *"$ext") return 0 ;; esac
  done <<< "$(get reports.mediaExtensions)"
  return 1
}

keep_dir=$(mktemp -d)
up_dir=$(mktemp -d)
trap 'rm -rf "$keep_dir" "$up_dir"' EXIT
keep_n=0
up_n=0
while IFS= read -r f; do
  rel=${f#"$src"/}
  case "$persist" in
    all) bucket=keep ;;
    none) bucket=up ;;
    except-media) if is_media "$rel"; then bucket=up; else bucket=keep; fi ;;
  esac
  if [ "$bucket" = keep ]; then
    mkdir -p "$keep_dir/$(dirname "$rel")"; cp "$f" "$keep_dir/$rel"; keep_n=$((keep_n+1))
  else
    mkdir -p "$up_dir/$(dirname "$rel")"; cp "$f" "$up_dir/$rel"; up_n=$((up_n+1))
  fi
done < <(find "$src" -type f)

if [ "$up_n" -gt 0 ]; then
  case "$provider" in
    none)
      echo "blob.provider=none; discarding $up_n report file(s) (not kept, not uploaded)" >&2 ;;
    aws)
      : "${DRP_S3_BUCKET:?aws provider requires DRP_S3_BUCKET}"
      command -v aws >/dev/null || { echo "aws CLI not installed" >&2; exit 2; }
      aws s3 cp "$up_dir" "s3://$DRP_S3_BUCKET/$prefix/" --recursive || { echo "S3 upload failed" >&2; exit 4; }
      echo "uploaded $up_n file(s) to s3://$DRP_S3_BUCKET/$prefix/" ;;
    azure)
      : "${DRP_AZURE_CONTAINER:?azure provider requires DRP_AZURE_CONTAINER}"
      if [ -z "${AZURE_STORAGE_CONNECTION_STRING:-}" ] && \
         { [ -z "${AZURE_STORAGE_ACCOUNT:-}" ] || [ -z "${AZURE_STORAGE_KEY:-}" ]; }; then
        echo "azure provider requires AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT+AZURE_STORAGE_KEY" >&2
        exit 2
      fi
      command -v az >/dev/null || { echo "az CLI not installed" >&2; exit 2; }
      az storage blob upload-batch -d "$DRP_AZURE_CONTAINER" --destination-path "$prefix" \
        -s "$up_dir" --overwrite >/dev/null || { echo "Azure upload failed" >&2; exit 4; }
      echo "uploaded $up_n file(s) to azure://$DRP_AZURE_CONTAINER/$prefix/" ;;
  esac
fi

if [ "$persist" != "none" ] && [ "$keep_n" -gt 0 ]; then
  dest="$repo/$persist_path"
  mkdir -p "$dest"
  cp -r "$keep_dir/." "$dest/"
  git -C "$repo" add -- "$persist_path"
  echo "kept $keep_n report file(s) in $persist_path"
fi

old_head=$(git -C "$repo" rev-parse --short HEAD)
last_msg=$(git -C "$repo" log -1 --format=%s 2>/dev/null || echo "")
if git -C "$repo" diff --cached --quiet; then
  echo "commit unchanged ($old_head); no reports to add per persistInRepo=$persist"
elif [ "${last_msg#release-candidate:}" != "$last_msg" ]; then
  git -C "$repo" commit -q --amend --no-edit
  echo "amended release candidate commit $old_head -> $(git -C "$repo" rev-parse --short HEAD)"
else
  git -C "$repo" commit -q -m "release-candidate: $release_id"
  echo "created release candidate commit $(git -C "$repo" rev-parse --short HEAD)"
fi

while IFS= read -r f; do rm -f "$f"; done < <(find "$src" -type f)
find "$src" -type d -empty -delete 2>/dev/null || true
echo "finalize done: kept=$keep_n uploaded/discarded=$up_n provider=$provider"
