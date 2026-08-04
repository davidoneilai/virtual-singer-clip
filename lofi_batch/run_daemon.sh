#!/usr/bin/env bash
# Wait for a free GPU, then run one daily job; loop forever.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GPU="${GPU:-1}"
POLL="${DAEMON_POLL_SECONDS:-300}"
UTIL_MAX="${GPU_FREE_UTIL_MAX:-5}"
MEM_MIN="${GPU_FREE_MEM_MIB_MIN:-20000}"

if [ -f lofi_batch/config.env ]; then
  set -a
  # shellcheck disable=SC1091
  source lofi_batch/config.env
  set +a
fi

echo "Daemon watching GPU $GPU (poll=${POLL}s util_max=${UTIL_MAX} mem_min=${MEM_MIN})"
while true; do
  if python lofi_batch/gpu_free.py --gpu "$GPU" --util-max "$UTIL_MAX" --mem-free-min-mib "$MEM_MIN"; then
    echo "GPU free — starting daily job $(date -Iseconds)"
    SKIP_UPLOAD="${SKIP_UPLOAD:-0}" bash lofi_batch/run_daily.sh || echo "daily job failed: $?"
    echo "Sleeping ${POLL}s after job..."
  else
    echo "GPU busy — sleep ${POLL}s"
  fi
  sleep "$POLL"
done
