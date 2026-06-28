#!/usr/bin/env bash
# Isolated conda env for MuseTalk (legacy lip-sync fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MT_ENV="${VSC_MUSETALK_CONDA_ENV:-$ROOT/musetalk/conda-env}"
MT_PYTHON="${MT_ENV}/bin/python"
MT_PIP="${MT_ENV}/bin/pip"
REPO="${VSC_MUSETALK_REPO:-$ROOT/external/MuseTalk}"
MARKER="${VSC_CACHE_DIR:-$ROOT/.cache}/musetalk_env_ok"

smoke_test() {
  "$MT_PYTHON" - <<'PY'
import cv2, torch
print("musetalk env ok — torch", torch.__version__)
PY
}

if [ -f "$MARKER" ] && smoke_test 2>/dev/null; then
  echo "MuseTalk env already OK: $MT_ENV"
  exit 0
fi

if [ ! -d "$REPO/.git" ]; then
  echo "Cloning MuseTalk into $REPO ..."
  git clone https://github.com/TMElyralab/MuseTalk "$REPO"
fi

if [ ! -x "$MT_PYTHON" ]; then
  echo "Creating MuseTalk conda env at $MT_ENV ..."
  conda create -y -p "$MT_ENV" python=3.10 pip
fi

echo "Installing MuseTalk runtime packages ..."
"$MT_PIP" install -U "pip>=24,<25"
"$MT_PIP" install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu130
"$MT_PIP" install -r requirements-musetalk-runtime.txt

echo "Installing OpenMMLab (may compile mmcv from source) ..."
"$MT_PIP" install -U openmim
"$MT_ENV/bin/mim" install mmengine || true
"$MT_ENV/bin/mim" install "mmcv>=2.0.1,<2.2.0" || true
"$MT_ENV/bin/mim" install "mmdet>=3.0.0,<3.3.0" || true
"$MT_ENV/bin/mim" install "mmpose>=1.1.0,<1.4.0" || true

UNET="$REPO/models/musetalkV15/unet.pth"
if [ ! -f "$UNET" ]; then
  echo "MuseTalk weights missing. Run: bash scripts/download_musetalk_weights.sh"
fi

smoke_test || {
  echo "WARNING: MuseTalk env incomplete (OpenMMLab may have failed)."
  exit 1
}
date -Iseconds > "$MARKER"
echo "MuseTalk ready: $MT_PYTHON"
