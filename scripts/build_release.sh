#!/usr/bin/env bash
# Build the frontend and package the plugin into <slug>.zip.
set -euo pipefail

cd "$(dirname "$0")/.."

PLUGIN_NAME="Smart TV Controls"
SLUG="$(echo "$PLUGIN_NAME" | tr '[:upper:] ' '[:lower:]-')"
# Stable name (no version) so /releases/latest/download/<slug>.zip is a permanent URL.
# The release version is carried by the git tag / release title, not the filename.
ZIP_NAME="${SLUG}.zip"

command -v pnpm >/dev/null || { echo "pnpm is required"; exit 1; }

echo "Vendoring Python dependencies..."
bash scripts/vendor_python.sh

echo "Building frontend..."
pnpm install
pnpm run build

STAGING="$(mktemp -d)/${PLUGIN_NAME}"
mkdir -p "$STAGING"

echo "Staging ${PLUGIN_NAME}..."
cp -RL \
  dist \
  backend \
  py_modules \
  main.py \
  plugin.json \
  package.json \
  README.md \
  LICENSE \
  "$STAGING"

rm -f "$STAGING/dist/"*.map
find "$STAGING/backend" -type d -name tests -prune -exec rm -rf {} +
find "$STAGING" -type d -name __pycache__ -prune -exec rm -rf {} +

echo "Zipping ${ZIP_NAME}..."
ROOT="$(pwd)"
rm -f "$ZIP_NAME"
(cd "$(dirname "$STAGING")" && zip -rq "$ROOT/$ZIP_NAME" "$PLUGIN_NAME")

echo "Done: ${ZIP_NAME}"
