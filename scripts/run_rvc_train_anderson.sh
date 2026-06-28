#!/usr/bin/env bash
# Train RVC model for Anderson on GPU 4 (detached Docker job).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${VSC_DOCKER_IMAGE:-a4898b757eac}"
GPU="${VSC_RVC_GPU:-4}"
EXP="${VSC_RVC_EXP:-anderson}"
SOURCE="${VSC_RVC_SOURCE:-assets/anderson.wav}"
EPOCHS="${VSC_RVC_EPOCHS:-200}"
CONTAINER="vsc-rvc-${EXP}"

docker rm -f "$CONTAINER" 2>/dev/null || true

docker run -d --name "$CONTAINER" \
  --gpus "device=${GPU}" \
  -e HF_HOME=/workspace/.cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface/hub \
  -w /workspace \
  -v "${ROOT}:/workspace" \
  "$IMAGE" \
  bash -lc "
    set -euo pipefail
    exec > >(tee -a output/rvc_${EXP}_train.log) 2>&1
    echo '=== RVC train ${EXP} GPU ${GPU} \$(date -Iseconds) ==='

    bash scripts/ensure_deps.sh

    DATASET=assets/voices/${EXP}/dataset
    mkdir -p \"\$DATASET\"

    if [ ! -f assets/voices/${EXP}/train_vocals.wav ]; then
      echo '=== Preparing vocal dataset (Demucs — before RVC deps) ==='
      python scripts/prepare_rvc_dataset.py \
        --source ${SOURCE} \
        --out-dir \"\$DATASET\" \
        --isolate-vocals \
        --device cuda:0
      cp \"\$DATASET\"/*.wav assets/voices/${EXP}/train_vocals.wav
    else
      echo '=== Reusing prepared vocals ==='
      cp assets/voices/${EXP}/train_vocals.wav \"\$DATASET/${EXP}.wav\"
    fi

    bash scripts/setup_rvc.sh

    echo '=== Training RVC (Python 3.10 env) ==='
    rvc/conda-env/bin/python scripts/rvc_train.py \
      --dataset-dir \"\$DATASET\" \
      --exp-name ${EXP} \
      --sample-rate 48k \
      --version v2 \
      --epochs ${EPOCHS} \
      --batch-size 12 \
      --save-every 50 \
      --gpu 0

    echo '=== Done \$(date -Iseconds) ==='
  "

echo "RVC training started: container=$CONTAINER gpu=$GPU"
echo "Logs: tail -f ${ROOT}/output/rvc_${EXP}_train.log"
echo "       docker logs -f $CONTAINER"
