#!/usr/bin/env bash
# Modão goiano with Anderson voice reference + caipira avatar (separate from Sabrina assets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash scripts/ensure_deps.sh

VARIANT="anderson_modao_goiano"
OUT="output/variants/$VARIANT"
REF="assets/anderson.wav"
AVATAR_DIR="assets/avatars/anderson_caipira"
AVATAR_VIDEO="$AVATAR_DIR/avatar.mp4"
AVATAR_IMAGE="$AVATAR_DIR/avatar.png"
CLIP_MODE="${VSC_CLIP_MODE:-hybrid}"
WITH_VC="${VSC_VOICE_CONVERSION:-0}"
VOICE_ENGINE="${VSC_VOICE_ENGINE:-seedvc}"
RVC_VOICE="${VSC_RVC_VOICE:-anderson}"

mkdir -p "$OUT/scenes" "$OUT/stems" "$OUT/voice_conversion" "$AVATAR_DIR"

echo "=== Variant: $VARIANT ==="
echo "Output dir: $OUT"
echo "Voice reference: $REF"
echo "Avatar (isolated): $AVATAR_IMAGE"
echo "Clip mode: $CLIP_MODE"
echo "(Sabrina avatar preserved at assets/avatar.png — not touched)"

python scripts/00_generate_lyrics.py \
  --language pt \
  --genre modao-goiano \
  --theme "um caipira goiano na estrada de terra, saudade de quem ficou no cerrado, viola na madrugada e copo de café amargo no boteco" \
  --out "$OUT/lyrics.txt"

python scripts/01_generate_song_acestep.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/song.wav" \
  --duration 150 \
  --vocal-language pt \
  --reference-audio "$REF" \
  --audio-cover-strength "${VSC_AUDIO_COVER_STRENGTH:-0.72}" \
  --prompt "modao goiano, sertanejo de raiz, viola caipira, sanfona, male vocalist, voz rouca e emotiva, guitarras acusticas, ritmo de chao batido, clima de cerrado, boteco, saudade, autentico e melancolico, studio quality"

python scripts/02_split_stems_demucs.py \
  --song "$OUT/song.wav" \
  --out-dir "$OUT/stems" \
  --vocals-out "$OUT/vocals.wav" \
  --instrumental-out "$OUT/instrumental.wav"

if [ "$WITH_VC" = "1" ]; then
  if [ "$VOICE_ENGINE" = "rvc" ]; then
    python scripts/03_convert_voice_rvc.py \
      --source "$OUT/vocals.wav" \
      --out "$OUT/converted_vocal.wav" \
      --voice "$RVC_VOICE"
  else
    python scripts/03_convert_voice_seedvc.py \
      --source "$OUT/vocals.wav" \
      --target "$REF" \
      --out "$OUT/converted_vocal.wav" \
      --tmp-dir "$OUT/voice_conversion"
  fi
  FINAL_MODE="remix-converted"
else
  echo "Skipping voice conversion (set VSC_VOICE_CONVERSION=1, VSC_VOICE_ENGINE=rvc after RVC train)."
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
  --visual-style "modao goiano music video, cerrado landscape at golden hour, dirt road, rustic wooden bar, male caipira singer with viola, cowboy hat, warm dusty tones, authentic Brazilian countryside, cinematic 24fps, 720p"

source scripts/hybrid_video_steps.sh
if [ "$CLIP_MODE" = "hybrid" ]; then
  run_hybrid_video_steps "$OUT" \
    "Brazilian caipira man close-up portrait, goiano cowboy, weathered kind face, straw hat, plaid shirt, cerrado golden hour light, looking at camera, shoulders visible, authentic sertanejo singer, cinematic 720p photorealistic" \
    "$AVATAR_VIDEO" \
    "$AVATAR_IMAGE"
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
echo "Audio only: $OUT/final_audio.wav"
echo "Avatar saved at: $AVATAR_IMAGE"
