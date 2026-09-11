#!/bin/bash
# Push Thumper game directory to the iPhone's Madeira.app Documents container.
# Game ends up at C:\Program Files\Thumper\ from Wine's perspective
# (Documents/wine/drive_c/Program Files/Thumper/ on the device filesystem).
#
# This is the dev-iteration path. For distribution, the game would be bundled
# in the .app and extracted on first launch via PrefixExtractor (TODO).
#
# Usage: bash scripts/deploy-thumper.sh [SRC_DIR [DEVICE_ID [BUNDLE_ID]]]
# Defaults honor THUMPER_SRC_DIR / DEVICE_ID / BUNDLE_ID for local iteration
# without editing the script.
set -euo pipefail

DEVICE_ID="${2:-${DEVICE_ID:-}}"
BUNDLE_ID="${3:-${BUNDLE_ID:-com.madeira.emulator}}"
SRC_DIR="${1:-${THUMPER_SRC_DIR:-}}"
DST_PATH='Documents/wine/drive_c/Program Files/Thumper'

if [[ -z "$SRC_DIR" ]]; then
    echo "Usage: bash $0 SRC_DIR [DEVICE_ID [BUNDLE_ID]]" >&2
    echo "  or set THUMPER_SRC_DIR (and optionally DEVICE_ID)." >&2
    exit 2
fi
if [[ -z "$DEVICE_ID" ]]; then
    echo "DEVICE_ID is required (arg or env)." >&2
    exit 2
fi

if [[ ! -d "$SRC_DIR" ]]; then
    echo "Source directory not found: $SRC_DIR"
    exit 1
fi

echo "==> Source: $SRC_DIR ($(du -sh "$SRC_DIR" | awk '{print $1}'))"
echo "==> Destination: <app container>/$DST_PATH"
echo ""

# devicectl copy doesn't auto-create parent dirs; create them by pushing
# a placeholder first if needed. Instead, the simplest reliable approach is
# to push the entire Thumper folder under "Program Files/" — the parent
# "wine/drive_c/Program Files/" should already exist after first Madeira
# launch (the prefix extractor creates drive_c/ and standard subdirs).
#
# devicectl behaves like cp -R when the source is a directory.

echo "==> Pushing game directory (this can take 30-60s for ~870MB)..."
xcrun devicectl device copy to \
    --device "$DEVICE_ID" \
    --source "$SRC_DIR" \
    --destination "$DST_PATH" \
    --domain-type appDataContainer \
    --domain-identifier "$BUNDLE_ID"

echo ""
echo "==> Done. Tap 'Run Thumper (D3D11 / win10)' in the Madeira app to launch."
