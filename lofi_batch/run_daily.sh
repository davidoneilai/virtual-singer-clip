#!/usr/bin/env bash
# Daily: generate one package then try upload (respects daily cap).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MODE=daily
export COUNT=1
export SKIP_UPLOAD="${SKIP_UPLOAD:-0}"
exec bash lofi_batch/run_docker.sh
