#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENDOR_DIR="$PROJECT_DIR/vendor/llama.cpp"
BUILD_DIR="$VENDOR_DIR/build"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "This bootstrap is intended for Apple Silicon macOS." >&2
  exit 1
fi

for tool in git cmake clang python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
done

python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.venv/bin/python" -m pip install -e "$PROJECT_DIR[dev]"

if [ ! -d "$VENDOR_DIR/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$VENDOR_DIR"
fi

cmake -S "$VENDOR_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_METAL=ON \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF

BUILD_JOBS=$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || sysctl -n hw.ncpu)
cmake --build "$BUILD_DIR" --config Release --target llama-server -j "$BUILD_JOBS"

echo "Bootstrap complete. Next: place a GGUF model in $PROJECT_DIR/models and run make doctor."
