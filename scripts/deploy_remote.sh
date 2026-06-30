#!/usr/bin/env bash
# Build and install the plugin onto a Steam Deck over SSH.
# Override the target with env vars, e.g. DECK_HOST=192.168.1.50 ./scripts/deploy_remote.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PLUGIN_NAME="DeckaTV"
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

# Multiplex one SSH connection so the password is typed once: the first ssh
# opens a master connection (and creates the dest dir), then rsync reuses it
# without re-prompting.
echo "Syncing to ${DECK_USER}@${DECK_HOST}:${DEST} (enter the Deck password when prompted)..."
SSH_CTRL="$(mktemp -u)"
trap 'ssh -o ControlPath="$SSH_CTRL" -O exit "${DECK_USER}@${DECK_HOST}" 2>/dev/null || true' EXIT
ssh -o ControlMaster=auto -o ControlPath="$SSH_CTRL" -o ControlPersist=60 \
  -o StrictHostKeyChecking=accept-new \
  "${DECK_USER}@${DECK_HOST}" "mkdir -p '${DEST}'"
rsync -rv --delete \
  -e "ssh -o ControlPath='${SSH_CTRL}'" \
  "$STAGING/" "${DECK_USER}@${DECK_HOST}:${DEST// /\\ }/"

echo "Done. Restart Decky (or reload the plugin) on the Deck to pick up changes."
