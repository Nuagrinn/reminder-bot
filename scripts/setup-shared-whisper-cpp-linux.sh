#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-medium}"
INSTALL_DIR="${ASSISTANT_WHISPER_CPP_DIR:-/opt/assistant-shared/whisper.cpp}"
SRC_DIR="$INSTALL_DIR/src"
BUILD_DIR="$INSTALL_DIR/build"
BIN_DIR="$INSTALL_DIR/bin"
MODEL_DIR="$INSTALL_DIR/models"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$MODEL_DIR"

if [ ! -d "$SRC_DIR/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$SRC_DIR"
else
  git -C "$SRC_DIR" pull --ff-only
fi

cmake -S "$SRC_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --config Release -j "$(nproc)"

WHISPER_BIN="$(find "$BUILD_DIR" -type f -name whisper-cli | head -n 1)"
if [ -z "$WHISPER_BIN" ]; then
  echo "whisper-cli was not found after build" >&2
  exit 1
fi
cp "$WHISPER_BIN" "$BIN_DIR/whisper-cli"
chmod +x "$BIN_DIR/whisper-cli"

MODEL_PATH="$MODEL_DIR/ggml-$MODEL.bin"
if [ ! -f "$MODEL_PATH" ]; then
  curl -L --fail \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$MODEL.bin" \
    -o "$MODEL_PATH"
fi

cat <<EOF
STT_PROVIDER=whisper_cpp
STT_WHISPER_CPP_BIN=$BIN_DIR/whisper-cli
STT_WHISPER_CPP_MODEL=$MODEL_PATH
EOF
