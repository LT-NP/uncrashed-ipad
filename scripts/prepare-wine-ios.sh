#!/bin/bash
# Shared, real Wine inputs for the iOS native libraries and optional DXMT PE build.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WINE_SRC="$REPO_ROOT/wine"
WINE_BUILD="$WINE_SRC/build-macos"
MINGW_VERSION=20260421
MINGW_DIR="$REPO_ROOT/toolchains/llvm-mingw-$MINGW_VERSION-ucrt-macos-universal"
DXMT_PE=0
case "${1:-}" in
    "") ;;
    --dxmt-pe) DXMT_PE=1 ;;
    *) echo "Usage: $0 [--dxmt-pe]" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "Usage: $0 [--dxmt-pe]" >&2; exit 2; }

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "ERROR: Wine iOS preparation requires an Apple Silicon Mac with Xcode." >&2
    exit 1
fi
[[ -f "$WINE_SRC/configure" ]] || { echo "ERROR: initialize the wine submodule first." >&2; exit 1; }
JOBS="${JOBS:-${BUILD_JOBS:-}}"
if [[ -z "$JOBS" ]]; then
    JOBS="$(sysctl -n hw.ncpu)"
fi
xcrun --sdk iphoneos --show-sdk-version

if [[ ! -x "$MINGW_DIR/bin/aarch64-w64-mingw32-clang" ]]; then
    mkdir -p "$REPO_ROOT/toolchains"
    download="$(mktemp -d "${TMPDIR:-/tmp}/wine-mingw.XXXXXX")"
    trap 'rm -rf "$download"' EXIT
    curl --fail --silent --show-error --location --retry 3 \
        --connect-timeout 30 --max-time 600 --proto '=https' --proto-redir '=https' \
        "https://github.com/mstorsjo/llvm-mingw/releases/download/$MINGW_VERSION/llvm-mingw-$MINGW_VERSION-ucrt-macos-universal.tar.xz" \
        -o "$download/llvm-mingw.tar.xz"
    tar -xJf "$download/llvm-mingw.tar.xz" -C "$REPO_ROOT/toolchains"
fi
export PATH="$MINGW_DIR/bin:$PATH"
for tool in aarch64-w64-mingw32-clang llvm-dlltool llvm-ar lld; do
    [[ -x "$MINGW_DIR/bin/$tool" ]] || { echo "ERROR: incomplete llvm-mingw: $tool missing." >&2; exit 1; }
done
aarch64-w64-mingw32-clang --version

# Re-run configure even after cache restoration: config.h alone says nothing
# about the source revision, selected architecture, SDK or generated IDL headers.
mkdir -p "$WINE_BUILD"
(
    cd "$WINE_BUILD"
    CC="$(xcrun --sdk macosx --find clang)" \
    CXX="$(xcrun --sdk macosx --find clang++)" \
    ../configure --enable-win64 --enable-archs=aarch64 --with-mingw=llvm-mingw \
        --without-x --without-freetype --without-vulkan --disable-tests \
        --prefix=/tmp/wine-ios
) 2>&1 | tee "$REPO_ROOT/wine-configure.log"
make -C "$WINE_BUILD" -j"$JOBS" include/all 2>&1 | tee "$REPO_ROOT/wine-headers-build.log"
for header in config.h dwrite.h dwrite_3.h; do
    [[ -s "$WINE_BUILD/include/$header" ]] || { echo "ERROR: generated Wine header missing: $header" >&2; exit 1; }
done
bash "$REPO_ROOT/build/freetype-ios/build.sh" 2>&1 | tee "$REPO_ROOT/freetype-build.log"

if [[ "$DXMT_PE" == 1 ]]; then
    # These are PE/COFF libraries, not the iOS Mach-O archives. Always rebuild
    # their final outputs so old scaffolding archives/scripts cannot satisfy make.
    targets=(
        tools/winebuild/winebuild
        libs/winecrt0/aarch64-windows/libwinecrt0.a
        dlls/ntdll/aarch64-windows/libntdll.a
        dlls/dbghelp/aarch64-windows/libdbghelp.a
    )
    for target in "${targets[@]}"; do rm -f "$WINE_BUILD/$target"; done
    make -C "$WINE_BUILD" -j"$JOBS" "${targets[@]}" 2>&1 | tee "$REPO_ROOT/wine-dxmt-pe-build.log"
    "$WINE_BUILD/tools/winebuild/winebuild" --version
    for target in "${targets[@]:1}"; do
        # llvm-ar must be able to read actual members; eight-byte placeholders fail.
        members="$("$MINGW_DIR/bin/llvm-ar" t "$WINE_BUILD/$target")"
        [[ -n "$members" ]] || { echo "ERROR: empty Wine PE archive: $target" >&2; exit 1; }
    done
fi
