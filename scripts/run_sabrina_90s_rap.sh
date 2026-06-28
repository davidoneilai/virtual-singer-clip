#!/usr/bin/env bash
# 90s pop-rap test with English lyrics + Sabrina reference voice.
# Writes everything to output/variants/sabrina_90s_rap/ — does not touch output/ root files.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash scripts/ensure_deps.sh

VARIANT="sabrina_90s_rap"
OUT="output/variants/$VARIANT"
REF_DIR="assets/references/sabrina"
REF_TAG="${VSC_REFERENCE_TAG:-rap}"
CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
WITH_VC="${VSC_VOICE_CONVERSION:-0}"
mkdir -p "$OUT/scenes" "$OUT/stems" "$OUT/voice_conversion" "$REF_DIR"

if [ -z "$(find "$REF_DIR" -maxdepth 1 -name '*.wav' -print -quit)" ]; then
  cp -n assets/sabrina.wav "$REF_DIR/rap_acapella.wav" 2>/dev/null || true
  cp -n assets/sabrina-espresso.wav "$REF_DIR/espresso_acapella.wav" 2>/dev/null || true
fi

echo "=== Variant: $VARIANT ==="
echo "Output dir: $OUT"
echo "(Original samba-pop run stays in output/ — archive with: bash scripts/archive_output.sh samba_pop_pt)"

export VSC_LYRICS_HUB_CACHE="${VSC_LYRICS_HUB_CACHE:-/raid/user_davidoneil/.cache/hub}"

python scripts/00_generate_lyrics.py \
  --language en \
  --theme "a confident young woman owning the night, 90s bubblegum pop meets hip-hop swagger" \
  --out "$OUT/lyrics.txt"

python scripts/01_generate_song_acestep.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/song.wav" \
  --duration 90 \
  --vocal-language en \
  --reference-dir "$REF_DIR" \
  --reference-tag "$REF_TAG" \
  --audio-cover-strength "${VSC_AUDIO_COVER_STRENGTH:-0.55}" \
  --prompt "90s pop-rap, female vocalist, boom bap drums, funky bassline, playful rap verses, catchy sung hook, MTV era energy, studio quality, bright mix"

python scripts/02_split_stems_demucs.py \
  --song "$OUT/song.wav" \
  --out-dir "$OUT/stems" \
  --vocals-out "$OUT/vocals.wav" \
  --instrumental-out "$OUT/instrumental.wav"

if [ "$WITH_VC" = "1" ]; then
  python scripts/03_convert_voice_seedvc.py \
    --source "$OUT/vocals.wav" \
    --target "$REF_DIR/rap_acapella.wav" \
    --out "$OUT/converted_vocal.wav" \
    --tmp-dir "$OUT/voice_conversion"
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
  --mode "$FINAL_MODE"

python scripts/05_make_scene_prompts.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/scenes.json" \
  --num-scenes "${VSC_NUM_BROLL_SCENES:-6}" \
  --visual-style "1990s MTV music video, neon colors, baggy fashion, boombox, roller rink at night, young female rapper performing, fisheye lens, VHS grain, high detail, 24fps, 720p"

source scripts/hybrid_video_steps.sh
if [ "$CLIP_MODE" = "hybrid" ]; then
  run_hybrid_video_steps "$OUT" \
    "1990s MTV music video close-up portrait, young female pop-rap singer, neon lighting, confident expression, looking at camera, shoulders visible, VHS grain, cinematic 720p"
else
  python scripts/06_generate_video_wan.py \
    --scenes "$OUT/scenes.json" \
    --out-dir "$OUT/scenes"
  python scripts/08_assemble_clip.py \
    --scenes-dir "$OUT/scenes" \
    --audio "$OUT/final_audio.wav" \
    --out "$OUT/final_videoclip.mp4"
fi

echo "Done: $OUT/final_videoclip.mp4"
