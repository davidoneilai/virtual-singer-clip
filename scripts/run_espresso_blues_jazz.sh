#!/usr/bin/env bash
# Espresso lyrics — American blues (virtual singer character, strong vocal).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash scripts/ensure_deps.sh

VARIANT="espresso_blues_jazz"
OUT="output/variants/$VARIANT"
REF_DIR="assets/references/sabrina"
REF_TAG="${VSC_REFERENCE_TAG:-}"
CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
WITH_VC="${VSC_VOICE_CONVERSION:-0}"

AVATAR_DIR="assets/avatars/sabrina_blues"
AVATAR_VIDEO="$AVATAR_DIR/avatar.mp4"
AVATAR_IMAGE="$AVATAR_DIR/avatar.png"

MUSIC_PROMPT="Chicago electric blues, powerful female vocalist, gritty soulful belting, raw emotional delivery, overdriven blues guitar, Hammond organ, punchy backbeat drums, walking bass, smoky juke joint atmosphere, vocal-forward mix, 12-bar blues groove, live club energy, studio quality"
SCENE_STYLE="American blues club music video, Chicago juke joint, warm amber and deep blue lighting, Black female blues singer at vintage microphone, electric guitar and Hammond organ, sweat and raw emotion, close-up powerful performance, gritty cinematic film grain, 24fps, 720p"
AVATAR_PROMPT="American blues music video close-up portrait, Black female blues singer, powerful expressive face, vintage silver microphone, warm amber stage lighting, emotional intensity, looking at camera, shoulders visible, photorealistic original virtual character, cinematic 720p"
PERF_PROMPT="Black female blues singer performing passionately in a smoky Chicago blues club, vintage microphone, amber stage lights, powerful belting, electric guitar in background, cinematic concert energy"

mkdir -p "$OUT/scenes" "$OUT/stems" "$OUT/voice_conversion" "$REF_DIR" "$AVATAR_DIR"

echo "=== Variant: $VARIANT (American blues) ==="
echo "Output dir: $OUT"
echo "Reference library: $REF_DIR"
echo "Avatar: $AVATAR_IMAGE"
echo "Clip mode: $CLIP_MODE | Lipsync: ${VSC_LIPSYNC_BACKEND:-latentsync}"

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
  --audio-cover-strength "${VSC_AUDIO_COVER_STRENGTH:-0.42}" \
  --prompt "$MUSIC_PROMPT"

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
  --vocal-volume 1.55 \
  --instrumental-volume 0.62

python scripts/05_make_scene_prompts.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/scenes.json" \
  --num-scenes "${VSC_NUM_BROLL_SCENES:-6}" \
  --visual-style "$SCENE_STYLE"

export VSC_REGENERATE_AVATAR="${VSC_REGENERATE_AVATAR:-1}"
source scripts/hybrid_video_steps.sh

if [ "$CLIP_MODE" = "wan" ]; then
  python scripts/render_video.py \
    --out-dir "$OUT" \
    --avatar-image "$AVATAR_IMAGE" \
    --avatar-video "$AVATAR_VIDEO" \
    --avatar-prompt "$AVATAR_PROMPT" \
    --performance-prompt "$PERF_PROMPT"
else
  run_video_steps "$OUT" "$AVATAR_PROMPT" "$AVATAR_VIDEO" "$AVATAR_IMAGE" "$PERF_PROMPT"
fi

echo "Done: $OUT/final_videoclip.mp4"
echo "Hybrid: $OUT/final_video_hybrid.mp4"
echo "Audio: $OUT/final_audio.wav"
