#!/usr/bin/env bash
# Isolated conda env for EchoMimicV2 / EchoMimicV3 avatar performance.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EM_ENV="${VSC_ECHOMIMIC_CONDA_ENV:-$ROOT/echomimic/conda-env}"
EM_PYTHON="${EM_ENV}/bin/python"
EM_PIP="${EM_ENV}/bin/pip"
V2_REPO="$ROOT/external/echomimic_v2"
V3_REPO="$ROOT/external/echomimic_v3"
MARKER="${VSC_CACHE_DIR:-$ROOT/.cache}/echomimic_env_ok"
BACKEND="${VSC_AVATAR_BACKEND:-echomimic_v2}"

smoke_test() {
  "$EM_PYTHON" - <<'PY'
import torch, diffusers
assert torch.cuda.is_available()
print("echomimic env ok — torch", torch.__version__)
PY
}

if [ -f "$MARKER" ] && smoke_test 2>/dev/null; then
  echo "EchoMimic env already OK: $EM_ENV"
  exit 0
fi

if [ ! -d "$V2_REPO/.git" ]; then
  git clone https://github.com/antgroup/echomimic_v2 "$V2_REPO"
fi
if [ ! -d "$V3_REPO/.git" ]; then
  git clone https://github.com/antgroup/echomimic_v3 "$V3_REPO"
fi

if [ ! -x "$EM_PYTHON" ]; then
  echo "Creating EchoMimic conda env at $EM_ENV ..."
  conda create -y -p "$EM_ENV" python=3.10 pip
fi

echo "Installing EchoMimic runtime packages ..."
"$EM_PIP" install -U "pip>=24,<25"
"$EM_PIP" install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu130
"$EM_PIP" install -r requirements-echomimic-runtime.txt

if [ ! -d "$V2_REPO/pretrained_weights" ]; then
  echo "Downloading EchoMimicV2 weights (large) ..."
  git clone https://huggingface.co/BadToBest/EchoMimicV2 "$V2_REPO/pretrained_weights" || true
fi

if [ "$BACKEND" = "echomimic_v3" ] || [ ! -d "$V3_REPO/flash/transformer" ]; then
  if [ ! -d "$V3_REPO/flash" ]; then
    echo "Download EchoMimicV3 weights into $V3_REPO/flash manually if missing:"
    echo "  huggingface-cli download BadToBest/EchoMimicV3 --local-dir $V3_REPO/flash"
  fi
fi

smoke_test
date -Iseconds > "$MARKER"
echo "EchoMimic ready: $EM_PYTHON"
