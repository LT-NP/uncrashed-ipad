#!/bin/bash
# Build the four aarch64 Windows DLLs required by DXMT inside Wine.
set -euo pipefail

BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"
DXMT_ROOT="$REPO_ROOT/research/dxmt"
WINE_BUILD="$REPO_ROOT/wine/build-macos"
MINGW="$REPO_ROOT/toolchains/llvm-mingw-20260421-ucrt-macos-universal"
PE_BUILD="$BUILD_DIR/pe"
JOBS="${JOBS:-3}"

for tool in meson ninja xcrun python3; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
test -x "$MINGW/bin/aarch64-w64-mingw32-clang"
test -x "$WINE_BUILD/tools/winebuild/winebuild"
test -s "$DXMT_ROOT/include/native/directx/d3d11.h"
# Reject old setup-only dummy archives before Meson can accidentally accept them.
for archive in "$WINE_BUILD/libs/winecrt0/aarch64-windows/libwinecrt0.a" \
               "$WINE_BUILD/dlls/ntdll/aarch64-windows/libntdll.a" \
               "$WINE_BUILD/dlls/dbghelp/aarch64-windows/libdbghelp.a"; do
    test -s "$archive" || { echo "Missing $archive; run scripts/prepare-wine-ios.sh --dxmt-pe" >&2; exit 1; }
    members=$("$MINGW/bin/aarch64-w64-mingw32-ar" t "$archive")
    [[ -n "$members" ]] || { echo "Empty Wine import archive: $archive" >&2; exit 1; }
done

export SDKROOT
# The native compiler below is invoked by absolute path (no default sysroot),
# so SDKROOT alone is not enough to find system headers — the Wine host-tools
# build failed exactly this way. Resolve once, verify up front, and pass
# -isysroot explicitly in the Meson native file (harmless if redundant).
MACOS_SDK="$(xcrun --sdk macosx --show-sdk-path)"
if [[ -z "$MACOS_SDK" || ! -d "$MACOS_SDK" ]]; then
    echo "ERROR: macOS SDK not found (xcrun returned '${MACOS_SDK:-<empty>}')." >&2
    exit 1
fi
if [[ ! -f "$MACOS_SDK/usr/include/stdio.h" ]]; then
    echo "ERROR: macOS SDK has no usr/include/stdio.h: $MACOS_SDK" >&2
    exit 1
fi
echo "macOS SDK: $MACOS_SDK"
SDKROOT="$MACOS_SDK"
export PATH="$MINGW/bin:$PATH"
APPLE_CLANG=$(xcrun --find clang)
APPLE_CLANGXX=$(xcrun --find clang++)

# Explicit binary paths avoid source-tree symlinks and accidental selection
# of llvm-mingw's clang as the native macOS compiler.
python3 - "$BUILD_DIR" "$MINGW" "$APPLE_CLANG" "$APPLE_CLANGXX" "$MACOS_SDK" <<'PY'
import sys
from pathlib import Path

build, mingw = map(Path, sys.argv[1:3])
sdk = sys.argv[5]
def quote(value):
    return "'" + str(value).replace('\\', '\\\\').replace("'", "\\'") + "'"

cross = ['[binaries]']
for key, binary in [('c', 'clang'), ('cpp', 'clang++'), ('ar', 'ar'),
                    ('strip', 'strip'), ('windres', 'windres')]:
    cross.append(f'{key} = {quote(mingw / "bin" / ("aarch64-w64-mingw32-" + binary))}')
cross += [f"xcrun = ['/bin/bash', {quote(build / 'xcrun-ios-shaders.sh')}]",
          '', '[properties]', 'needs_exe_wrapper = true', '', '[host_machine]',
          "system = 'windows'", "cpu_family = 'aarch64'", "cpu = 'aarch64'", "endian = 'little'"]
(build / 'aarch64-windows.ini').write_text('\n'.join(cross) + '\n')
sysroot = ['-isysroot', sdk]
(build / 'macos-native.ini').write_text(
    f'[binaries]\nc = {quote(sys.argv[3])}\ncpp = {quote(sys.argv[4])}\n'
    f'\n[built-in options]\n'
    f'c_args = {sysroot}\n'
    f'cpp_args = {sysroot}\n'
    f'c_link_args = {sysroot}\n'
    f'cpp_link_args = {sysroot}\n')
PY

# macOS still ships Bash 3.2, where expanding an empty array with `set -u`
# aborts with "unbound variable". Spell out the two Meson invocations so the
# first clean build works as well as a reconfiguration of an existing tree.
if [[ -f "$PE_BUILD/meson-private/coredata.dat" ]]; then
    meson setup --reconfigure --cross-file "$BUILD_DIR/aarch64-windows.ini" \
        --native-file "$BUILD_DIR/macos-native.ini" --buildtype release \
        "-Dwine_build_path=$WINE_BUILD" "$PE_BUILD" "$DXMT_ROOT"
else
    meson setup --cross-file "$BUILD_DIR/aarch64-windows.ini" \
        --native-file "$BUILD_DIR/macos-native.ini" --buildtype release \
        "-Dwine_build_path=$WINE_BUILD" "$PE_BUILD" "$DXMT_ROOT"
fi
meson compile -C "$PE_BUILD" -j "$JOBS"

python3 - "$REPO_ROOT/tools/validate-ios-bundle.py" "$PE_BUILD" <<'PY'
import runpy
import sys
from pathlib import Path

validate = runpy.run_path(sys.argv[1])['pe']
build = Path(sys.argv[2])
for directory, name in [('d3d11', 'd3d11'), ('dxgi', 'dxgi'),
                        ('winemetal', 'winemetal'), ('d3d10', 'd3d10core')]:
    path = build / 'src' / directory / f'{name}.dll'
    validate(path.read_bytes(), 0xAA64)
    print(f'Validated ARM64 PE DLL: {path}')
PY

mkdir -p "$REPO_ROOT/app/Madeira/aarch64-windows"
cp "$PE_BUILD/src/d3d11/d3d11.dll" "$PE_BUILD/src/dxgi/dxgi.dll" \
    "$PE_BUILD/src/winemetal/winemetal.dll" "$PE_BUILD/src/d3d10/d3d10core.dll" \
    "$REPO_ROOT/app/Madeira/aarch64-windows/"
