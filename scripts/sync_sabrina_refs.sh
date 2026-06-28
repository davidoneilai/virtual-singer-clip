#!/usr/bin/env bash
# Sync the four Sabrina acapella clips into assets/references/sabrina/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF_DIR="$ROOT/assets/references/sabrina"
mkdir -p "$REF_DIR"

for name in manchild nonsense please sabrina-espresso; do
  src="$ROOT/assets/${name}.wav"
  if [ ! -f "$src" ]; then
    echo "Missing reference clip: $src" >&2
    exit 1
  fi
  dst="$REF_DIR/${name}.wav"
  if [ "$src" -nt "$dst" ] || [ ! -f "$dst" ]; then
    cp -f "$src" "$dst"
    echo "Synced $dst"
  fi
done

# Drop legacy copies so only the four curated clips are combined.
rm -f "$REF_DIR/espresso_acapella.wav" "$REF_DIR/general_acapella.wav" 2>/dev/null || true

echo "Reference library ready: $REF_DIR ($(find "$REF_DIR" -maxdepth 1 -name '*.wav' | wc -l) files)"
