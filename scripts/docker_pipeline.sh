#!/usr/bin/env bash
# Run inside the GPU container (detached). Logs everything to output/pipeline.log.
set -euo pipefail

cd /workspace
mkdir -p output
LOG=output/pipeline.log
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date -Iseconds) start pid=$$ ==="

bash "$(dirname "$0")/ensure_deps.sh"

STEPS=("$@")
if [ "${#STEPS[@]}" -eq 0 ]; then
  STEPS=(scripts/06_generate_video_wan.py scripts/08_assemble_clip.py)
fi

for step in "${STEPS[@]}"; do
  echo "--- running $step ---"
  python "$step"
done

echo "=== $(date -Iseconds) done ==="
