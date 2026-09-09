#!/bin/bash
# Build the pinned, unmodified FEX fork's static iOS libraries for Madeira.
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
if [[ "$(uname -s)" != Darwin ]]; then
    echo 'This step requires a Mac with Xcode (a GitHub macOS runner works).' >&2
    exit 1
fi
for tool in cmake ninja python3 xcrun; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
[[ -f FEX/CMakeLists.txt ]] || { echo 'Initialize the pinned FEX submodule first.' >&2; exit 1; }
# Clean any stale build dir from a previous failed run – CMake caches
# IOS sysroot paths that change between runner images.
rm -rf FEX/build-ios
SYSROOT="$(xcrun --sdk iphoneos --show-sdk-path)"
[[ -d "$SYSROOT" ]] || { echo "iphoneos SDK not found at $SYSROOT" >&2; exit 1; }
echo "Using SDK: $SYSROOT ($(xcrun --sdk iphoneos --show-sdk-version))"
cmake -S FEX -B FEX/build-ios -G Ninja \
    -DCMAKE_SYSTEM_NAME=iOS \
    -DCMAKE_SYSTEM_PROCESSOR=arm64 \
    -DCMAKE_OSX_ARCHITECTURES=arm64 \
    -DCMAKE_OSX_SYSROOT="$SYSROOT" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=18.0 \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER="$(xcrun --sdk iphoneos --find clang)" \
    -DCMAKE_CXX_COMPILER="$(xcrun --sdk iphoneos --find clang++)" \
    -DCMAKE_CXX_FLAGS="-DFEX_IOS_HOST=1" \
    -DCMAKE_DISABLE_FIND_PACKAGE_fmt=ON \
    -DCMAKE_DISABLE_FIND_PACKAGE_range-v3=ON \
    -DCMAKE_DISABLE_FIND_PACKAGE_unordered_dense=ON \
    -DBUILD_TESTING=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_THUNKS=OFF \
    -DENABLE_LTO=OFF -DENABLE_CCACHE=OFF \
    -DENABLE_GDB_SYMBOLS=OFF -DENABLE_OFFLINE_TELEMETRY=OFF \
    -DTUNE_CPU=none -DTUNE_ARCH=generic
cmake --build FEX/build-ios --parallel "${BUILD_JOBS:-3}" \
    --target FEXCore FEXCore_Base fmt cephes_128bit xxhash softfloat_3e JemallocLibs
for library in \
    FEXCore/Source/libFEXCore.a \
    FEXCore/Source/libFEXCore_Base.a \
    FEXCore/Source/libJemallocLibs.a \
    External/fmt/libfmt.a \
    External/cephes/libcephes_128bit.a \
    External/xxhash/cmake_unofficial/libxxhash.a \
    External/SoftFloat-3e/libsoftfloat_3e.a; do
    xcrun lipo -verify_arch arm64 "FEX/build-ios/$library"
done
echo 'FEX static libraries built for arm64. Device execution is not tested by this build.'
