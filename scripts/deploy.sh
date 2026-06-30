#!/usr/bin/env bash
# Build and install the plugin into the local Decky homebrew directory.
set -euo pipefail

cd "$(dirname "$0")/.."

PLUGIN_NAME="DeckaTV"
DEST="$HOME/homebrew/plugins/${PLUGIN_NAME}"

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

echo "Syncing to ${DEST}..."
mkdir -p "$DEST"
rsync -rv --delete "$STAGING/" "$DEST/"

echo "Done."
