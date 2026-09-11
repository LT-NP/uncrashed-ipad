#!/bin/bash
# Create CI-only placeholder static libs so xcodebuild -showBuildSettings
# and check-build-inputs can be validated without waiting for Wine/DXMT/LLVM.
# Real artifacts (fex-ios-arm64, gnutls-ios-arm64) overwrite these when built.
# Placeholders use correct ar magic '!<arch>\n' so check-build-inputs sees 'present',
# not 'invalid_archive'. Not for device testing.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$REPO_ROOT/app/Madeira"
mkdir -p "$REPO_ROOT/app/Madeira/x86_64-vcruntime"
mkdir -p "$REPO_ROOT/toolchains/gnutls-ios/lib"

# Dummy ar for missing Wine/DXMT libs — 8-byte magic only.
# check-build-inputs reports these as 'present' for dry-run Xcode validation,
# but validate-ios-bundle.py rejects them ('empty/placeholder archive'): they
# must be overwritten by real builds before any device IPA. Re-running this
# helper never overwrites an existing file, real or placeholder.
make_dummy_ar() {
  local out="$1"
  if [[ -f "$out" ]]; then echo "keep $out"; return; fi
  printf '!<arch>\n' > "$out"
  echo "created placeholder $out (CI dry-run only; real build must overwrite)"
}

# Wine/DXMT libs expected by Xcode
for lib in libwineserver.a libntdll_unix.a libwin32u_unix.a libdxmt_combined.a libgnutls.a libhogweed.a libnettle.a libgmp.a; do
  make_dummy_ar "$REPO_ROOT/app/Madeira/$lib"
  # Also ensure toolchain copy for gnutls consumers
  if [[ "$lib" == libgmp.a || "$lib" == libhogweed.a || "$lib" == libnettle.a || "$lib" == libgnutls.a ]]; then
    make_dummy_ar "$REPO_ROOT/toolchains/gnutls-ios/lib/$lib"
  fi
done

# VCRuntime DLLs — need non-empty file with MZ header for PE check (size>0)
for dll in msvcp140.dll vcruntime140.dll vcruntime140_1.dll; do
  p="$REPO_ROOT/app/Madeira/x86_64-vcruntime/$dll"
  if [[ ! -s "$p" ]]; then
    printf 'MZ\x90\x00placeholder' > "$p"
    echo "created placeholder $p"
  else
    echo "keep $p"
  fi
done

# Ensure extra vcruntime files that fetch-vcruntime expects exist as placeholders too
for dll in concrt140.dll msvcp140_codecvt_ids.dll vcamp140.dll vccorlib140.dll vcomp140.dll msvcp140_1.dll msvcp140_2.dll msvcp140_atomic_wait.dll vcruntime140_threads.dll; do
  p="$REPO_ROOT/app/Madeira/x86_64-vcruntime/$dll"
  [[ -f "$p" ]] || printf 'MZ\x90\x00placeholder' > "$p"
done

# cacert.pem is tracked but ensure non-empty
[[ -s "$REPO_ROOT/app/Madeira/cacert.pem" ]] || echo "# placeholder cacert" > "$REPO_ROOT/app/Madeira/cacert.pem"

echo "CI placeholders ready. Real builds overwrite them."
