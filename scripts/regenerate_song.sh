#!/usr/bin/env bash
# Re-generate only song.wav for a variant (after reference vocal fix / strength sweep).
set -euo pipefail

VARIANT="${1:?usage: regenerate_song.sh VARIANT [cover_strength]}"
STRENGTH="${2:-0.72}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="output/variants/$VARIANT"

if [ ! -f "$OUT/lyrics.txt" ]; then
  echo "Missing $OUT/lyrics.txt — run full pipeline first." >&2
  exit 1
fi

case "$VARIANT" in
  anderson_modao_goiano)
    REF=(--reference-audio assets/anderson.wav)
    PROMPT="modao goiano, sertanejo de raiz, viola caipira, sanfona, male vocalist, voz rouca e emotiva, guitarras acusticas, ritmo de chao batido, clima de cerrado, boteco, saudade, autentico e melancolico, studio quality"
    LANG=pt
    DUR=150
    ;;
  espresso_dark_rock)
    bash scripts/sync_sabrina_refs.sh
    REF=(--reference-dir assets/references/sabrina)
    PROMPT="dark rock pop, female vocalist, distorted electric guitars, heavy punchy drums, gritty bass, raw aggressive energy, moody dark atmosphere, powerful chorus, industrial edge, vocal-forward mix, studio quality"
    LANG=en
    DUR=175
    ;;
  espresso_blues_jazz)
    REF=(--reference-dir assets/references/sabrina --reference-tag espresso)
    PROMPT="slow blues jazz, smoky female vocalist, expressive vocal runs and ad-libs, intimate jazz club, piano, upright bass, brushed drums, warm reverb, vocal-forward mix, soulful and playful, studio quality"
    LANG=en
    DUR=175
    ;;
  sabrina_sao_joao_quadrilha)
    REF=(--reference-dir assets/references/sabrina)
    PROMPT="festa junina São João quadrilha, forró pé de serra autêntico, sanfona melódica, zabumba marcante, triângulo e pandeiro, ritmo animado de quadrilha, female vocalist, coro festivo de arraial, energia de baile junino, vocal jovial e saltitante, nordeste brasileiro, vocal-forward mix, studio quality"
    LANG=en
    DUR=150
    ;;
  *)
    echo "Unknown variant: $VARIANT" >&2
    exit 1
    ;;
esac

python scripts/01_generate_song_acestep.py \
  --lyrics "$OUT/lyrics.txt" \
  --out "$OUT/song.wav" \
  --duration "$DUR" \
  --vocal-language "$LANG" \
  "${REF[@]}" \
  --audio-cover-strength "$STRENGTH" \
  --prompt "$PROMPT"

python scripts/04_finalize_audio.py \
  --song "$OUT/song.wav" \
  --out "$OUT/final_audio.wav" \
  --mode song

echo "Regenerated: $OUT/song.wav + $OUT/final_audio.wav (strength=$STRENGTH)"
echo "Prepared ref: $OUT/reference_prepared.wav"
