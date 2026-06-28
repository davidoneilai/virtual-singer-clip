#!/usr/bin/env bash
# Isolated conda env for Hallo3 cinematic avatar.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

H3_ENV="${VSC_HALLO3_CONDA_ENV:-$ROOT/hallo3/conda-env}"
H3_PYTHON="${H3_ENV}/bin/python"
H3_PIP="${H3_ENV}/bin/pip"
REPO="$ROOT/external/hallo3"
MARKER="${VSC_CACHE_DIR:-$ROOT/.cache}/hallo3_env_ok"

smoke_test() {
  "$H3_PYTHON" - <<'PY'
import torch
assert torch.cuda.is_available()
print("hallo3 env ok — torch", torch.__version__)
PY
}

if [ -f "$MARKER" ] && smoke_test 2>/dev/null; then
  echo "Hallo3 env already OK: $H3_ENV"
  exit 0
fi

if [ ! -d "$REPO/.git" ]; then
  git clone https://github.com/fudan-generative-vision/hallo3 "$REPO"
fi

if [ ! -x "$H3_PYTHON" ]; then
  echo "Creating Hallo3 conda env at $H3_ENV ..."
  conda create -y -p "$H3_ENV" python=3.10 pip
fi

echo "Installing Hallo3 packages ..."
"$H3_PIP" install -U "pip>=24,<25"
"$H3_PIP" install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu130

if [ -f "$REPO/requirements.txt" ]; then
  "$H3_PIP" install -r "$REPO/requirements.txt" || "$H3_PIP" install diffusers transformers accelerate omegaconf
fi

MODELS="$REPO/pretrained_models"
if [ ! -d "$MODELS" ]; then
  echo "Downloading Hallo3 pretrained models (very large) ..."
  huggingface-cli download fudan-generative-ai/hallo3 --local-dir "$MODELS" || true
fi

smoke_test
date -Iseconds > "$MARKER"
echo "Hallo3 ready: $H3_PYTHON"
