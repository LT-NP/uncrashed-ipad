#!/bin/bash
# Copy a complete user-owned game installation into an initialized Madeira prefix.
set -euo pipefail
if [[ $# -ne 3 ]]; then
    echo "Usage: bash $0 GAME_DIRECTORY DEVICE_ID INSTALLED_BUNDLE_ID" >&2
    exit 2
fi
game_dir="$1"
device_id="$2"
bundle_id="$3"
if [[ ! -f "$game_dir/Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe" ]]; then
    echo "Missing shipping executable in the supplied game directory." >&2
    exit 1
fi
xcrun devicectl device copy to \
    --device "$device_id" \
    --source "$game_dir" \
    --destination 'Documents/wine/drive_c/Program Files/Uncrashed FPV Drone Sim' \
    --domain-type appDataContainer \
    --domain-identifier "$bundle_id"
echo "Copy completed. Enable JIT, then select Uncrashed (UE4, DirectX 11)."
