#!/usr/bin/env bash
# Vendor pure-Python runtime dependencies into py_modules/ (arch-independent).
set -euo pipefail

cd "$(dirname "$0")/.."

WEBSOCKETS_VERSION="14.2"
TARGET="py_modules"

rm -rf "$TARGET"
python3 -m pip install "websockets==${WEBSOCKETS_VERSION}" --target "$TARGET" --no-compile --quiet
find "$TARGET" -name '*.so' -delete
rm -rf "$TARGET"/*.dist-info
find "$TARGET" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "Vendored websockets==${WEBSOCKETS_VERSION} into ${TARGET}/"
