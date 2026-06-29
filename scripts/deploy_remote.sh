#!/usr/bin/env bash
# Build and install the plugin onto a Steam Deck over SSH.
# Override the target with env vars, e.g. DECK_HOST=192.168.1.50 ./scripts/deploy_remote.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PLUGIN_NAME="Smart TV Controls"
DECK_USER="${DECK_USER:-deck}"
DECK_HOST="${DECK_HOST:-steamdeck.lan}"
DEST="/home/${DECK_USER}/homebrew/plugins/${PLUGIN_NAME}"

command -v pnpm >/dev/null || { echo "pnpm is required"; exit 1; }
command -v rsync >/dev/null || { echo "rsync is required"; exit 1; }

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

# Single SSH connection: --rsync-path creates the dest dir, so the password is typed once.
echo "Syncing to ${DECK_USER}@${DECK_HOST}:${DEST} (enter the Deck password when prompted)..."
rsync -rv --delete \
  --rsync-path="mkdir -p '${DEST}' && rsync" \
  -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$STAGING/" "${DECK_USER}@${DECK_HOST}:${DEST}/"

echo "Done. Restart Decky (or reload the plugin) on the Deck to pick up changes."
