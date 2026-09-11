#!/bin/bash
# Complete DXMT build, shared by the standalone and full IPA workflows.
set -euo pipefail
BUILD_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$BUILD_DIR/../.." && pwd)"

bash "$REPO_ROOT/scripts/prepare-wine-ios.sh" --dxmt-pe
bash "$BUILD_DIR/build-llvm.sh"
bash "$BUILD_DIR/build-pe.sh"
bash "$BUILD_DIR/build.sh"
