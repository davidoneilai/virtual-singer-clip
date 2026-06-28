#!/usr/bin/env bash
# Isolated conda env for LatentSync 1.6 lip-sync.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source scripts/ensure_git.sh

LS_ENV="${VSC_LATENTSYNC_CONDA_ENV:-$ROOT/latentsync/conda-env}"
LS_PYTHON="${LS_ENV}/bin/python"
LS_PIP="${LS_ENV}/bin/pip"
REPO="${VSC_LATENTSYNC_REPO:-$ROOT/external/LatentSync}"
MARKER="${VSC_CACHE_DIR:-$ROOT/.cache}/latentsync_env_ok"

install_system_libs() {
  if ! command -v apt-get >/dev/null 2>&1; then
    return 0
  fi
  apt-get update -qq
  apt-get install -y -qq \
    git \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgl1 \
    || true
}

fix_opencv() {
  # face-alignment/mediapipe may pull opencv-python (needs libGL); force headless.
  "$LS_PIP" uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true
  "$LS_PIP" install --force-reinstall "opencv-python-headless>=4.9.0"
}

smoke_test() {
  "$LS_PYTHON" - <<'PY'
import cv2, torch
import diffusers
print("latentsync env ok — torch", torch.__version__, "cv2", cv2.__version__)
PY
}

download_checkpoints() {
  echo "Downloading LatentSync 1.6 checkpoints via huggingface_hub ..."
  REPO="$REPO" HF_TOKEN="${HF_TOKEN:-}" "$LS_PYTHON" - <<'PY'
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

repo = Path(os.environ["REPO"])
ckpt_dir = repo / "checkpoints"
ckpt_dir.mkdir(parents=True, exist_ok=True)
token = os.environ.get("HF_TOKEN") or None

for filename in ("latentsync_unet.pt", "whisper/tiny.pt"):
    path = hf_hub_download(
        repo_id="ByteDance/LatentSync-1.6",
        filename=filename,
        local_dir=str(ckpt_dir),
        token=token,
    )
    print("downloaded", path)
PY
}

if [ -f "$MARKER" ] && smoke_test 2>/dev/null; then
  echo "LatentSync env already OK: $LS_ENV"
  exit 0
fi

install_system_libs

if [ ! -f "$REPO/scripts/inference.py" ]; then
  clone_repo_if_missing "https://github.com/bytedance/LatentSync" "$REPO" || {
    echo "LatentSync repo missing at $REPO"
    echo "On the host run: bash setup_external.sh"
    exit 1
  }
fi

if [ ! -x "$LS_PYTHON" ]; then
  echo "Creating LatentSync conda env at $LS_ENV ..."
  conda create -y -p "$LS_ENV" python=3.10 pip
fi

echo "Installing LatentSync packages into $LS_ENV ..."
"$LS_PIP" install -U "pip>=24,<25"
"$LS_PIP" install torch torchvision torchaudio \
  --index-url https://download.pytorch.org/whl/cu130
"$LS_PIP" install -r requirements-latentsync-runtime.txt
"$LS_PIP" install -U "huggingface_hub[cli]"
fix_opencv

CKPT="$REPO/checkpoints/latentsync_unet.pt"
WHISPER="$REPO/checkpoints/whisper/tiny.pt"
if [ ! -f "$CKPT" ] || [ ! -f "$WHISPER" ]; then
  download_checkpoints
fi

if [ ! -f "$CKPT" ]; then
  echo "ERROR: checkpoint missing at $CKPT"
  echo "Set HF_TOKEN and re-run: bash scripts/setup_latentsync.sh"
  exit 1
fi

smoke_test
date -Iseconds > "$MARKER"
echo "LatentSync ready: $LS_PYTHON"
