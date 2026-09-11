#!/bin/bash
# Build a tiny x86_64 PE for testing FEX on iOS.
# Usage: ./build.sh fib   (or any other .c file in this dir without extension)
set -euo pipefail

NAME="${1:-fib}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOLCHAIN="${TOOLCHAIN:-$REPO_ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal/bin}"
APP_BUNDLE="${APP_BUNDLE:-$REPO_ROOT/app/Madeira/arm64ec-windows}"

[[ -x "$TOOLCHAIN/x86_64-w64-mingw32-clang" ]] || { echo "ERROR: mingw clang not found in $TOOLCHAIN" >&2; exit 1; }
[[ -f "$NAME.c" ]] || { echo "ERROR: no such test source: $NAME.c" >&2; exit 1; }

cd "$(dirname "$0")"

echo "=== building $NAME.exe (x86_64 PE) ==="
"$TOOLCHAIN/x86_64-w64-mingw32-clang" \
    -O2 -g \
    -o "$NAME.exe" "$NAME.c" \
    -lkernel32

ls -la "$NAME.exe"

echo ""
echo "=== copying $NAME.exe to app bundle ==="
cp "$NAME.exe" "$APP_BUNDLE/$NAME.exe"
ls -la "$APP_BUNDLE/$NAME.exe"

echo ""
echo "=== checksum ==="
if command -v md5 >/dev/null; then
    md5 "$NAME.exe" "$APP_BUNDLE/$NAME.exe"
elif command -v md5sum >/dev/null; then
    md5sum "$NAME.exe" "$APP_BUNDLE/$NAME.exe"
fi

echo ""
echo "=== entry/main symbols ==="
"$TOOLCHAIN/x86_64-w64-mingw32-objdump" --syms "$NAME.exe" 2>&1 \
    | grep -E "_main|main$|mainCRTStartup|WinMainCRTStartup" | head -5

echo ""
echo "Done. Reminder: the iOS app picks the EXE based on the chosen target name."
echo "If $NAME.exe isn't auto-loaded, update WineProcessBridge.m or the launcher."
