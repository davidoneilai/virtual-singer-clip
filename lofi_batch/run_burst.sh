#!/usr/bin/env bash
# Burst: generate N packages into the queue; never bypass daily upload cap.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MODE=burst
export COUNT="${COUNT:-3}"
export SKIP_UPLOAD=1
exec bash lofi_batch/run_docker.sh
