#!/usr/bin/env bash
set -euo pipefail

# Determine target directory: argument if valid, else current pwd
if [[ -n "${1:-}" ]]; then
  if [[ -d "$1" ]]; then
    TARGET_DIR="$(cd "$1" && pwd)"
  else
    echo "Error: '$1' is not a valid directory" >&2
    exit 1
  fi
else
  TARGET_DIR="$PWD"
fi

# Change to script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Run uv run gamr with target dir
uv run gamr "$TARGET_DIR"
