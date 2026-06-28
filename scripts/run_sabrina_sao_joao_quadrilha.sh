#!/usr/bin/env bash
# Sabrina-style English lyrics — festa junina / quadrilha de São João (forró pé de serra).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash scripts/ensure_deps.sh

VARIANT="sabrina_sao_joao_quadrilha"
OUT="output/variants/$VARIANT"
REF_DIR="assets/references/sabrina"
REF_TAG="${VSC_REFERENCE_TAG:-}"
CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
WITH_VC="${VSC_VOICE_CONVERSION:-0}"

AVATAR_DIR="assets/avatars/sabrina_festa_junina"
AVATAR_VIDEO="$AVATAR_DIR/avatar.mp4"
AVATAR_IMAGE="$AVATAR_DIR/avatar.png"

MUSIC_PROMPT="festa junina São João quadrilha, forró pé de serra autêntico, sanfona melódica, zabumba marcante, triângulo e pandeiro, ritmo animado de quadrilha, female vocalist, coro festivo de arraial, energia de baile junino, vocal jovial e saltitante, nordeste brasileiro, vocal-forward mix, studio quality"
SCENE_STYLE="Brazilian festa junina São João music video, quadrilha dancers in colorful checkered costumes, bandeirinhas papel de arraial, milho e fogueira, sanfona and zabumba, young female singer leading the quadrilha, warm bonfire night lighting, joyful arraial atmosphere, cinematic 24fps, 720p"
AVATAR_PROMPT="Brazilian festa junina close-up portrait, young female singer in colorful quadrilha São João costume, checkered dress and ribbons, bandeirinha flags, warm bonfire glow, joyful playful expression, looking at camera, shoulders visible, photorealistic virtual character, cinematic 720p"
PERF_PROMPT="Young female singer performing at a Brazilian festa junina arraial, leading quadrilha dance with sanfona and zabumba, colorful São João decorations, bonfire lights, energetic festive performance"

mkdir -p "$OUT/scenes" "$OUT/stems" "$OUT/voice_conversion" "$REF_DIR" "$AVATAR_DIR"

echo "=== Variant: $VARIANT (São João quadrilha) ==="
echo "Output dir: $OUT"
echo "Reference library: $REF_DIR"
echo "Avatar: $AVATAR_IMAGE"
echo "Clip mode: $CLIP_MODE | Lipsync: ${VSC_LIPSYNC_BACKEND:-latentsync}"

cp assets/lyrics/sabrina_sao_joao.txt "$OUT/lyrics.txt"

REF_ARGS=(--reference-dir "$REF_DIR")
if [ -n "$REF_TAG" ]; then
  REF_ARGS+=(--reference-tag "$REF_TAG")
fi

python scripts/01_generate_song_acestep.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/song.wav" \
  --duration 150 \
  --vocal-language en \
  "${REF_ARGS[@]}" \
  --audio-cover-strength "${VSC_AUDIO_COVER_STRENGTH:-0.48}" \
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
  --vocal-volume 1.45 \
  --instrumental-volume 0.68

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
