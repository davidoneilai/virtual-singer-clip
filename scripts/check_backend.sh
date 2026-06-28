#!/usr/bin/env bash
# Generic backend readiness check.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND="${1:?usage: check_backend.sh latentsync|musetalk|echomimic_v2|echomimic_v3|hallo3}"
python scripts/select_video_backend.py --check "$BACKEND" >/dev/null
