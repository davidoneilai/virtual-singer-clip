#!/usr/bin/env bash
# Smoke test: tiny package → dry-run → optional real unlisted YouTube upload.
# Usage (from repo root):
#   bash lofi_batch/smoke_youtube_upload.sh           # dry-run only
#   bash lofi_batch/smoke_youtube_upload.sh --upload  # also publish unlisted
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GPU="${GPU:-1}"
IMAGE="${IMAGE:-a4898b757eac}"
CONTAINER="${CONTAINER:-experimento-david}"
DO_UPLOAD=0
PRIVACY="${YOUTUBE_PRIVACY:-unlisted}"

if [ -f lofi_batch/config.env ]; then
  # shellcheck disable=SC1091
  set -a
  source lofi_batch/config.env
  set +a
fi
CONTAINER="${CONTAINER:-experimento-david}"

for arg in "$@"; do
  case "$arg" in
    --upload) DO_UPLOAD=1 ;;
    --help|-h)
      echo "Usage: bash lofi_batch/smoke_youtube_upload.sh [--upload]"
      exit 0
      ;;
  esac
done

if [ ! -f lofi_batch/secrets/token.json ]; then
  echo "Missing lofi_batch/secrets/token.json — run: python lofi_batch/youtube_auth.py --manual"
  exit 1
fi
if [ ! -f lofi_batch/secrets/client_secret.json ]; then
  echo "Missing lofi_batch/secrets/client_secret.json"
  exit 1
fi

docker rm -f "$CONTAINER" 2>/dev/null || true

echo "Starting $CONTAINER on GPU $GPU (smoke YouTube; upload=$DO_UPLOAD privacy=$PRIVACY)"

docker run --rm --name "$CONTAINER" \
  --gpus "device=${GPU}" \
  -e PYTHONPATH=/workspace \
  -e YOUTUBE_PRIVACY="$PRIVACY" \
  -e DO_UPLOAD="$DO_UPLOAD" \
  -e VSC_CACHE_DIR=/workspace/.cache \
  -e HF_HOME=/workspace/.cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface/hub \
  -w /workspace \
  -v "${ROOT}:/workspace" \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    echo "=== smoke youtube $(date -Iseconds) ==="

    if ! command -v ffmpeg >/dev/null 2>&1; then
      apt-get update -qq && apt-get install -y -qq ffmpeg
    fi

    pip install -q -U pip
    pip install -q -r lofi_batch/requirements-youtube.txt

    export PYTHONPATH=/workspace
    PKG=output/lofi_batch/queue/smoke_test_upload
    mkdir -p "$PKG"

    echo "=== validate OAuth ==="
    python lofi_batch/youtube_auth.py --validate-only

    echo "=== build tiny package ==="
    ffmpeg -y -f lavfi -i color=c=blue:s=1280x720:d=1 -frames:v 1 "$PKG/cover.png"
    ffmpeg -y -f lavfi -i sine=f=440:d=8 "$PKG/playlist.wav"
    python lofi_batch/make_video.py --cover "$PKG/cover.png" --audio "$PKG/playlist.wav" --out "$PKG/video.mp4"

    python - <<PY
import json
from pathlib import Path
from lofi_batch.package import write_meta, mark_ready

p = Path("output/lofi_batch/queue/smoke_test_upload")
(p / "prompt.json").write_text(
    json.dumps(
        {
            "slug": "smoke_test_upload",
            "music_prompt": "test\n\nNEGATIVE PROMPT\nNO vocals",
            "image_prompt": "blue",
            "title": "SMOKE TEST — pode apagar",
            "description": "Upload de teste do pipeline lofi_batch. Pode deletar.",
            "tags": ["test", "lofi"],
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
write_meta(
    p,
    status="generating",
    title="SMOKE TEST — pode apagar",
    description="Upload de teste do pipeline lofi_batch. Pode deletar.",
    tags=["test", "lofi"],
)
mark_ready(p)
print("ready:", p)
PY

    echo "=== dry-run ==="
    python lofi_batch/youtube_upload.py --dry-run

    if [ "${DO_UPLOAD}" = "1" ]; then
      echo "=== real upload ($YOUTUBE_PRIVACY) ==="
      python lofi_batch/youtube_upload.py
      echo "=== state ==="
      cat output/lofi_batch/state.json 2>/dev/null || true
      ls -la output/lofi_batch/published/ 2>/dev/null || true
    else
      echo "Dry-run only. Re-run with --upload to publish unlisted."
    fi

    echo "=== smoke done $(date -Iseconds) ==="
  '
