#!/usr/bin/env bash
# Espresso lyrics — dark rock-pop, heavy/gritty production.
# Voice refs: manchild, nonsense, please, sabrina-espresso (combined automatically).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VIDEO_ONLY=0
for arg in "$@"; do
  if [ "$arg" = "--video-only" ]; then
    VIDEO_ONLY=1
  fi
done

bash scripts/ensure_deps.sh

VARIANT="espresso_dark_rock"
OUT="output/variants/$VARIANT"
REF_DIR="assets/references/sabrina"
REF_TAG="${VSC_REFERENCE_TAG:-}"
CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
WITH_VC="${VSC_VOICE_CONVERSION:-0}"
mkdir -p "$OUT/scenes" "$OUT/stems" "$OUT/voice_conversion"

echo "=== Variant: $VARIANT ==="
echo "Output dir: $OUT"
echo "Clip mode: $CLIP_MODE"
echo "Lipsync backend: ${VSC_LIPSYNC_BACKEND:-latentsync}"
echo "Avatar backend: ${VSC_AVATAR_BACKEND:-echomimic_v2}"

if [ "$VIDEO_ONLY" = "1" ]; then
  python scripts/render_video.py \
    --out-dir "$OUT" \
    --avatar-image "assets/avatar/reference.png" \
    --avatar-video "assets/avatar.mp4" \
    --avatar-prompt "dark rock music video close-up portrait, young female rock-pop singer, dramatic red and black lighting, edgy style, confident expression, looking at camera, shoulders visible, cinematic 720p" \
    --performance-prompt "A virtual rock-pop singer performing passionately on a dark gritty stage, red and black lighting, expressive gestures, cinematic concert energy."
  echo "Done: $OUT/final_videoclip.mp4"
  exit 0
fi

bash scripts/sync_sabrina_refs.sh

echo "Reference library: $REF_DIR (all clips combined)"

cp assets/lyrics/espresso.txt "$OUT/lyrics.txt"

REF_ARGS=(--reference-dir "$REF_DIR")
if [ -n "$REF_TAG" ]; then
  REF_ARGS+=(--reference-tag "$REF_TAG")
fi

python scripts/01_generate_song_acestep.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/song.wav" \
  --duration 175 \
  --vocal-language en \
  "${REF_ARGS[@]}" \
  --audio-cover-strength "${VSC_AUDIO_COVER_STRENGTH:-0.72}" \
  --prompt "dark rock pop, female vocalist, distorted electric guitars, heavy punchy drums, gritty bass, raw aggressive energy, moody dark atmosphere, powerful chorus, industrial edge, vocal-forward mix, studio quality"

python scripts/02_split_stems_demucs.py \
  --song "$OUT/song.wav" \
  --out-dir "$OUT/stems" \
  --vocals-out "$OUT/vocals.wav" \
  --instrumental-out "$OUT/instrumental.wav"

if [ "$WITH_VC" = "1" ]; then
  python scripts/03_convert_voice_seedvc.py \
    --source "$OUT/vocals.wav" \
    --target "$REF_DIR/sabrina-espresso.wav" \
    --out "$OUT/converted_vocal.wav" \
    --tmp-dir "$OUT/voice_conversion" \
    --cfg 0.55 \
    --steps 50
  FINAL_MODE="remix-converted"
else
  echo "Skipping Seed-VC. Set VSC_VOICE_CONVERSION=1 to enable."
  FINAL_MODE="song"
fi

python scripts/04_finalize_audio.py \
  --song "$OUT/song.wav" \
  --vocal "$OUT/vocals.wav" \
  --converted-vocal "$OUT/converted_vocal.wav" \
  --instrumental "$OUT/instrumental.wav" \
  --out "$OUT/final_audio.wav" \
  --mode "$FINAL_MODE" \
  --vocal-volume 1.35 \
  --instrumental-volume 0.75

python scripts/05_make_scene_prompts.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/scenes.json" \
  --num-scenes "${VSC_NUM_BROLL_SCENES:-6}" \
  --visual-style "dark rock music video, gritty urban stage, red and black lighting, female rock singer, electric guitar, heavy drums, smoke and strobe lights, cinematic aggressive performance, 24fps, 720p"

source scripts/hybrid_video_steps.sh
AVATAR_PROMPT="dark rock music video close-up portrait, young female rock-pop singer, dramatic red and black lighting, edgy style, confident expression, looking at camera, shoulders visible, cinematic 720p"
PERF_PROMPT="A virtual rock-pop singer performing passionately on a dark gritty stage, red and black lighting, expressive gestures, cinematic concert energy."

if [ "$CLIP_MODE" = "wan" ]; then
  python scripts/render_video.py \
    --out-dir "$OUT" \
    --avatar-prompt "$AVATAR_PROMPT" \
    --performance-prompt "$PERF_PROMPT"
else
  run_video_steps "$OUT" "$AVATAR_PROMPT" "assets/avatar.mp4" "assets/avatar/reference.png"
fi

echo "Done: $OUT/final_videoclip.mp4"
echo "Audio only: $OUT/final_audio.wav"
