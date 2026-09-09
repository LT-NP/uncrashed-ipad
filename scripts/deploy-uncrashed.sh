#!/bin/bash
# Copy a complete user-owned Uncrashed installation into an initialized Madeira prefix.
# Validates prerequisites before invoking Apple's devicectl (requires Xcode + initialized prefix).
set -euo pipefail
usage() {
    echo "Usage: bash $0 GAME_DIRECTORY DEVICE_ID INSTALLED_BUNDLE_ID" >&2
    echo "  GAME_DIRECTORY: path to 'Uncrashed FPV Drone Sim' (contains Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe)" >&2
    echo "  DEVICE_ID: from 'xcrun devicectl list devices' (e.g. 00008110-...)" >&2
    echo "  INSTALLED_BUNDLE_ID: e.g. com.example.Madeira (from xcodebuild or SideStore)" >&2
    exit 2
}
if [[ $# -ne 3 ]]; then usage; fi
game_dir="$1"
device_id="$2"
bundle_id="$3"

# Prerequisite checks (cheap, before 20GB copy)
command -v xcrun >/dev/null || { echo "xcrun not found — install Xcode." >&2; exit 1; }
if ! xcrun devicectl --version >/dev/null 2>&1; then echo "devicectl not available (Xcode 15+ required)." >&2; exit 1; fi
if [[ ! -d "$game_dir" ]]; then echo "GAME_DIRECTORY not a directory: $game_dir" >&2; exit 1; fi
exe="$game_dir/Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe"
if [[ ! -f "$exe" ]]; then echo "Missing shipping executable: $exe" >&2; exit 1; fi
# Quick size sanity (full game ~19GiB)
total_bytes=$(du -sb "$game_dir" 2>/dev/null | cut -f1 || du -sk "$game_dir" 2>/dev/null | awk '{print $1*1024}')
if [[ "$total_bytes" -lt 5000000000 ]]; then echo "Warning: game folder only $((total_bytes/1024/1024)) MiB — expected ~19 GiB, copy may be incomplete." >&2; fi
paks=$(find "$game_dir/Uncrashed/Content/Paks" -name '*.pak' 2>/dev/null | wc -l | tr -d ' ')
echo "Found $paks .pak files, total $((total_bytes/1024/1024/1024)) GiB"
# Bundle / device sanity
if ! xcrun devicectl list devices 2>/dev/null | grep -q "$device_id"; then
    echo "Warning: DEVICE_ID $device_id not in 'xcrun devicectl list devices' — check USB/WiFi pairing." >&2
fi

echo "Copying to device $device_id (app $bundle_id) — this takes minutes for 19 GiB..."
xcrun devicectl device copy to \
    --device "$device_id" \
    --source "$game_dir" \
    --destination 'Documents/wine/drive_c/Program Files/Uncrashed FPV Drone Sim' \
    --domain-type appDataContainer \
    --domain-identifier "$bundle_id"

echo "Copy completed. Next: enable JIT (StikDebug), then select Uncrashed (UE4, DirectX 11) in Madeira."
echo "Tip: check Documents/uncrashed-args.txt overrides and LogStore for first failure (Steam/d3d11/Jetsam)."
