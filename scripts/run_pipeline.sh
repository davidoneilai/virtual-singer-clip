#!/usr/bin/env bash
# Unified variant runner: audio pipeline + multi-backend video stage.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VARIANT="${1:?usage: run_pipeline.sh <variant>}"
shift || true

bash scripts/ensure_deps.sh

VIDEO_ONLY="${VSC_VIDEO_ONLY:-0}"
OUT="output/variants/$VARIANT"
if [ "$VIDEO_ONLY" = "1" ] || { [ -f "$OUT/final_audio.wav" ] && [ -f "$OUT/scenes.json" ] && [ "${VSC_FORCE_AUDIO:-0}" != "1" ]; }; then
  python scripts/render_video.py --out-dir "$OUT"
  exit 0
fi

case "$VARIANT" in
  espresso_dark_rock)
    bash scripts/run_espresso_dark_rock.sh
    ;;
  espresso_blues_jazz)
    bash scripts/run_espresso_blues_jazz.sh
    ;;
  sabrina_90s_rap)
    bash scripts/run_sabrina_90s_rap.sh
    ;;
  anderson_modao_goiano)
    bash scripts/run_anderson_modao_goiano.sh
    ;;
  sabrina_sao_joao_quadrilha)
    bash scripts/run_sabrina_sao_joao_quadrilha.sh
    ;;
  *)
    echo "Unknown variant: $VARIANT"
    exit 1
    ;;
esac
