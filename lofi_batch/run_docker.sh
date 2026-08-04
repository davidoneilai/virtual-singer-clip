#!/usr/bin/env bash
# Run Lo-Fi daily/burst pipeline inside a GPU Docker container.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GPU="${GPU:-1}"
IMAGE="${IMAGE:-a4898b757eac}"
CONTAINER="${CONTAINER:-vsc-lofi-batch}"
TRACKS="${TRACKS:-20}"
DURATION="${DURATION:-180}"
CONFIG_PATH="${CONFIG_PATH:-acestep-v15-xl-turbo}"
LM_MODEL="${LM_MODEL:-acestep-5Hz-lm-1.7B}"
BACKEND="${BACKEND:-pt}"
RUN_ID="${RUN_ID:-}"
FAIL_FAST="${FAIL_FAST:-0}"
MODE="${MODE:-daily}"
COUNT="${COUNT:-1}"
SKIP_UPLOAD="${SKIP_UPLOAD:-1}"
SKIP_COVER="${SKIP_COVER:-0}"
SKIP_VIDEO="${SKIP_VIDEO:-0}"
PROMPT_LLM_MODEL="${PROMPT_LLM_MODEL:-Qwen/Qwen3-4B-Instruct-2507}"

if [ -f lofi_batch/config.env ]; then
  # shellcheck disable=SC1091
  set -a
  source lofi_batch/config.env
  set +a
fi

docker rm -f "$CONTAINER" 2>/dev/null || true

echo "Starting $CONTAINER on GPU $GPU (mode=$MODE count=$COUNT tracks=$TRACKS duration=$DURATION)"

docker run -d --name "$CONTAINER" \
  --gpus "device=${GPU}" \
  -e VSC_CACHE_DIR=/workspace/.cache \
  -e HF_HOME=/workspace/.cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface/hub \
  -e TRACKS="$TRACKS" \
  -e DURATION="$DURATION" \
  -e CONFIG_PATH="$CONFIG_PATH" \
  -e LM_MODEL="$LM_MODEL" \
  -e BACKEND="$BACKEND" \
  -e FAIL_FAST="$FAIL_FAST" \
  -e MODE="$MODE" \
  -e COUNT="$COUNT" \
  -e SKIP_UPLOAD="$SKIP_UPLOAD" \
  -e SKIP_COVER="$SKIP_COVER" \
  -e SKIP_VIDEO="$SKIP_VIDEO" \
  -e PROMPT_LLM_MODEL="$PROMPT_LLM_MODEL" \
  ${RUN_ID:+-e RUN_ID="$RUN_ID"} \
  -w /workspace \
  -v "${ROOT}:/workspace" \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    mkdir -p output/lofi_batch
    exec > >(tee -a output/lofi_batch/docker_batch.log) 2>&1
    echo "=== lofi_batch pipeline $(date -Iseconds) mode=${MODE} ==="

    if ! command -v ffmpeg >/dev/null 2>&1; then
      apt-get update -qq && apt-get install -y -qq ffmpeg
    fi

    if ! python -c "import librosa, soundfile, diffusers, transformers" 2>/dev/null; then
      pip install -U pip
      pip install -r requirements.txt
      pip install -r requirements-acestep.txt
    fi

    EXTRA=()
    if [ "${FAIL_FAST:-0}" = "1" ]; then EXTRA+=(--fail-fast); fi
    if [ -n "${RUN_ID:-}" ]; then EXTRA+=(--run-id "$RUN_ID"); fi
    if [ "${SKIP_UPLOAD:-1}" = "1" ]; then EXTRA+=(--skip-upload); fi
    if [ "${SKIP_COVER:-0}" = "1" ]; then EXTRA+=(--skip-cover); fi
    if [ "${SKIP_VIDEO:-0}" = "1" ]; then EXTRA+=(--skip-video); fi

    python lofi_batch/run_pipeline.py \
      --mode "${MODE}" \
      --count "${COUNT}" \
      --tracks "${TRACKS}" \
      --duration "${DURATION}" \
      --config-path "${CONFIG_PATH}" \
      --lm-model "${LM_MODEL}" \
      --backend "${BACKEND}" \
      --prompt-model "${PROMPT_LLM_MODEL}" \
      "${EXTRA[@]}"

    echo "=== done $(date -Iseconds) ==="
  '

echo "Detached. Follow logs:"
echo "  docker logs -f $CONTAINER"
echo "  tail -f output/lofi_batch/docker_batch.log"
