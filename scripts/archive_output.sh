#!/usr/bin/env bash
# Copy current output/ to output/variants/<name> without deleting the original.
set -euo pipefail

NAME="${1:?usage: archive_output.sh <variant_name>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/output"
DEST="$ROOT/output/variants/$NAME"

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
mkdir -p "$DEST"
echo "Archiving $SRC -> $DEST"
for item in "$SRC"/*; do
  [ "$(basename "$item")" = "variants" ] && continue
  cp -a "$item" "$DEST/"
done
echo "Saved at $DEST"
