#!/usr/bin/env bash
# Hybrid / avatar video stage (delegates to render_video.py).
set -euo pipefail

run_hybrid_video_steps() {
  local out="$1"
  local avatar_prompt="${2:-music video close-up portrait, young female pop singer, confident expression, looking at camera, studio lighting, sharp face details, neutral background, shoulders visible, cinematic 24fps, 720p, photorealistic}"
  local avatar_video="${3:-assets/avatar.mp4}"
  local avatar_image="${4:-assets/avatar/reference.png}"
  local performance_prompt="${5:-$avatar_prompt}"

  if [ "${VSC_REGENERATE_AVATAR:-0}" = "1" ] || {
    [ ! -f "$avatar_image" ] && [ ! -f "$avatar_video" ] && [ ! -f "assets/avatar.png" ]
  }; then
    AVATAR_ARGS=(--prompt "$avatar_prompt" --out-video "$avatar_video" --out-image "$avatar_image")
    if [ "${VSC_REGENERATE_AVATAR:-0}" = "1" ]; then
      AVATAR_ARGS+=(--force)
    fi
    python scripts/06a_generate_avatar.py "${AVATAR_ARGS[@]}"
  else
    echo "Using avatar: $avatar_image (video: $avatar_video)"
  fi

  python scripts/render_video.py \
    --out-dir "$out" \
    --avatar-image "$avatar_image" \
    --avatar-video "$avatar_video" \
    --avatar-prompt "$avatar_prompt" \
    --performance-prompt "$performance_prompt"
}

run_video_steps() {
  local out="$1"
  local avatar_prompt="${2:-music video close-up portrait, virtual singer, cinematic 720p}"
  local avatar_video="${3:-assets/avatar.mp4}"
  local avatar_image="${4:-assets/avatar/reference.png}"
  local performance_prompt="${5:-$avatar_prompt}"

  run_hybrid_video_steps "$out" "$avatar_prompt" "$avatar_video" "$avatar_image" "$performance_prompt"
}
