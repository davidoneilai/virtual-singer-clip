#!/usr/bin/env bash
# Install pipeline Python deps once per fresh container.
set -euo pipefail

# Avoid CRLF breaking bash (e.g. pts.py: command not found).
if ls scripts/*.sh >/dev/null 2>&1; then
  sed -i 's/\r$//' scripts/*.sh 2>/dev/null || true
fi

if ! python -c "import diffusers" 2>/dev/null; then
  echo "Installing Python dependencies (fresh container)..."
  pip install -U pip
  pip install -r requirements.txt
  pip install -r requirements-acestep.txt
  pip install -r requirements-seedvc.txt
  pip install librosa
fi

if ! python -c "import imageio_ffmpeg" 2>/dev/null; then
  pip install imageio-ffmpeg
fi

if ! command -v ffmpeg >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq ffmpeg git libgl1 libglib2.0-0 || true
fi

CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
LIPSYNC_BACKEND="${VSC_LIPSYNC_BACKEND:-latentsync}"
AVATAR_BACKEND="${VSC_AVATAR_BACKEND:-echomimic_v2}"

setup_optional_backend() {
  local script="$1"
  if [ -f "scripts/$script" ]; then
    bash "scripts/$script" || echo "WARNING: $script failed (fallback may apply)."
  fi
}

case "$CLIP_MODE" in
  hybrid)
    if [ "$LIPSYNC_BACKEND" = "latentsync" ]; then
      setup_optional_backend setup_latentsync.sh
    elif [ "$LIPSYNC_BACKEND" = "musetalk" ]; then
      setup_optional_backend setup_musetalk.sh
    else
      setup_optional_backend setup_latentsync.sh
      setup_optional_backend setup_musetalk.sh
    fi
    ;;
  avatar)
    setup_optional_backend setup_echomimic.sh
    ;;
  cinematic_avatar)
    setup_optional_backend setup_hallo3.sh
    setup_optional_backend setup_echomimic.sh
    ;;
  wan)
    ;;
esac

# Legacy weight hint for MuseTalk fallback.
MUSETALK_UNET="external/MuseTalk/models/musetalkV15/unet.pth"
if [ "$CLIP_MODE" = "hybrid" ] && [ "$LIPSYNC_BACKEND" = "musetalk" ] && [ ! -f "$MUSETALK_UNET" ]; then
  echo "MuseTalk weights not found at $MUSETALK_UNET"
  echo "Download once with: bash scripts/download_musetalk_weights.sh"
fi
