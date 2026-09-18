#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 HUGGING_FACE_REPO GGUF_FILENAME" >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
mkdir -p "$PROJECT_DIR/models"

if command -v hf >/dev/null 2>&1; then
  hf download "$1" "$2" --local-dir "$PROJECT_DIR/models"
elif command -v huggingface-cli >/dev/null 2>&1; then
  huggingface-cli download "$1" "$2" --local-dir "$PROJECT_DIR/models"
elif command -v curl >/dev/null 2>&1; then
  TARGET="$PROJECT_DIR/models/$2"
  curl -fL --retry 3 --continue-at - \
    --output "$TARGET.partial" \
    "https://huggingface.co/$1/resolve/main/$2"
  mv "$TARGET.partial" "$TARGET"
else
  echo "Install curl or the Hugging Face CLI first." >&2
  exit 1
fi
