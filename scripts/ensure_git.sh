#!/usr/bin/env bash
# Ensure git exists when we need to clone external repos inside a container.
ensure_git() {
  if command -v git >/dev/null 2>&1; then
    return 0
  fi
  echo "git not found; trying to install ..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq git
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required but not available in this container."
    echo "Clone repos once on the host: bash setup_external.sh"
    return 1
  fi
}

clone_repo_if_missing() {
  local url="$1"
  local dest="$2"
  if [ -f "$dest/scripts/inference.py" ] || [ -f "$dest/infer.py" ] || [ -f "$dest/infer_flash.py" ]; then
    return 0
  fi
  ensure_git || return 1
  mkdir -p "$(dirname "$dest")"
  echo "Cloning $url into $dest ..."
  git clone --depth 1 "$url" "$dest"
}
