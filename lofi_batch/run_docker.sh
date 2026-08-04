#!/usr/bin/env bash
# Run lo-fi playlist batch inside a GPU Docker container.
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
SLUG="${SLUG:-}"

# Optional: source local overrides
if [ -f lofi_batch/config.env ]; then
  # shellcheck disable=SC1091
  set -a
  source lofi_batch/config.env
  set +a
fi

EXTRA_ARGS=()
if [ -n "$RUN_ID" ]; then
  EXTRA_ARGS+=(--run-id "$RUN_ID")
fi
if [ "$FAIL_FAST" = "1" ]; then
  EXTRA_ARGS+=(--fail-fast)
fi
if [ -n "$SLUG" ]; then
  EXTRA_ARGS+=(--slug "$SLUG")
fi

# output/ is often root-owned from prior containers; create inside the job instead
docker rm -f "$CONTAINER" 2>/dev/null || true

echo "Starting $CONTAINER on GPU $GPU (tracks=$TRACKS duration=$DURATION config=$CONFIG_PATH)"

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
  -e SLUG="$SLUG" \
  ${RUN_ID:+-e RUN_ID="$RUN_ID"} \
  -w /workspace \
  -v "${ROOT}:/workspace" \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail
    mkdir -p output/lofi_batch
    exec > >(tee -a output/lofi_batch/docker_batch.log) 2>&1
    echo "=== lofi_batch $(date -Iseconds) ==="

    if ! command -v ffmpeg >/dev/null 2>&1; then
      apt-get update -qq && apt-get install -y -qq ffmpeg
    fi

    if ! python -c "import librosa, soundfile, diffusers" 2>/dev/null; then
      pip install -U pip
      pip install -r requirements.txt
      pip install -r requirements-acestep.txt
    fi

    EXTRA=()
    if [ "${FAIL_FAST:-0}" = "1" ]; then EXTRA+=(--fail-fast); fi
    if [ -n "${RUN_ID:-}" ]; then EXTRA+=(--run-id "$RUN_ID"); fi
    if [ -n "${SLUG:-}" ]; then EXTRA+=(--slug "$SLUG"); fi

    python lofi_batch/run_batch.py \
      --tracks "${TRACKS}" \
      --duration "${DURATION}" \
      --config-path "${CONFIG_PATH}" \
      --lm-model "${LM_MODEL}" \
      --backend "${BACKEND}" \
      "${EXTRA[@]}"

    echo "=== done $(date -Iseconds) ==="
  '

echo "Detached. Follow logs:"
echo "  docker logs -f $CONTAINER"
echo "  tail -f output/lofi_batch/docker_batch.log"
