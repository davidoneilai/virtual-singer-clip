#!/usr/bin/env bash
# Isolated Python 3.10 env for RVC (fairseq breaks on 3.11 — no patches needed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RVC_ROOT="${VSC_RVC_ROOT:-rvc/RVC}"
RVC_ENV="${VSC_RVC_CONDA_ENV:-$ROOT/rvc/conda-env}"
export RVC_PYTHON="${RVC_ENV}/bin/python"
RVC_PIP="${RVC_ENV}/bin/pip"

if [ ! -f "$RVC_ROOT/infer-web.py" ]; then
  echo "RVC not found at $RVC_ROOT"
  exit 1
fi

if [ ! -x "$RVC_PYTHON" ]; then
  echo "Creating RVC conda env (Python 3.10) at $RVC_ENV ..."
  conda create -y -p "$RVC_ENV" python=3.10 pip
fi

echo "Installing RVC packages into $RVC_ENV ..."

# fairseq needs omegaconf 2.0.6; pip>=24.1 rejects its metadata — pin pip first.
"$RVC_PIP" install "pip==24.0"
"$RVC_PIP" install omegaconf==2.0.6 hydra-core==1.0.7
"$RVC_PIP" install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
"$RVC_PIP" install -r requirements-rvc-py310.txt

conda install -y -p "$RVC_ENV" -c conda-forge ffmpeg
"$RVC_PYTHON" scripts/patch_rvc_env.py

if ! "$RVC_PYTHON" -c "import scipy, fairseq, torch" 2>/dev/null; then
  echo "ERROR: RVC env still missing packages after install."
  "$RVC_PYTHON" -c "import scipy, fairseq, torch"
fi

"$RVC_PYTHON" -c "import fairseq, scipy, torch; print('RVC env ok — Python', __import__('sys').version.split()[0])"

HUBERT="$RVC_ROOT/assets/hubert/hubert_base.pt"
if [ ! -f "$HUBERT" ]; then
  echo "Downloading RVC pretrained assets..."
  (cd "$RVC_ROOT" && "$RVC_PYTHON" tools/download_models.py)
else
  echo "RVC assets already present at $RVC_ROOT/assets/"
fi

mkdir -p "$RVC_ROOT/assets/weights" "$RVC_ROOT/logs"
echo ""
echo "RVC ready. Use this Python for train/infer:"
echo "  $RVC_PYTHON"
