# IPA build audit — September 10, 2026

Authenticated inspection of [run 34445071135](https://github.com/LT-NP/uncrashed-ipad/actions/runs/34445071135), commit `632f572cd4990db50359fc1829dc7128a11eae2a`.

## Result

The run is green, but the uploaded IPA is not a runnable app. Its plist declares
`CFBundleExecutable = Madeira`, while `Payload/Madeira.app/Madeira` is absent.
This was verified directly in the downloaded IPA, not inferred from CI status.

The full job log explicitly contains `** BUILD FAILED **`. The workflow packages
the partial app directory anyway. Its shell pipelines do not reliably propagate
the failing compiler/build command status, and validation failures do not stop
artifact upload.

## Confirmed failures

- Xcode 16.4 / iPhoneOS 18.5 SDK compiled source using `glassEffect`; compilation
  fails in `ContentView.swift` at lines 572 and 2788. Select an SDK supporting
  those APIs, or add compile-time compatibility guards.
- Wine server build invokes a missing hard-coded
  `/opt/homebrew/Cellar/llvm/22.1.0/bin/llvm-objcopy`.
- ntdll compilation reports `dwrite_unixlib` failed, then archive creation fails
  because `dwrite_unixlib.o` is absent. The truncated command output does not
  expose the original compiler diagnostic.
- win32u reports 21 source compilations succeeded and 25 failed, and does not
  link. Individual `.err` files were not included in this IPA artifact.
- Wine server and ntdll output libraries remain eight-byte placeholders.
- The workflow creates a dummy DXMT archive, then prints `DXMT cached` and skips
  the DXMT build because its file-existence check accepts that dummy archive.
- All 12 files under the IPA's `x86_64-vcruntime/` directory are 15-byte dummy
  files. Existing ARM64/ARM64EC DLL resources do not replace these x64 inputs.
- The final architecture check reports that the Madeira executable does not
  exist, but the run still succeeds.

## Next development steps, in order

First local repair prepared after this audit: the IPA workflow explicitly selects
Xcode 26.3, uses Bash with pipeline error propagation, retains full diagnostics,
removes dummy-input creation and the DXMT existence-only shortcut, isolates its
DerivedData directory, and validates the executable and required PE resources
before and after packaging. `tools/validate-ios-bundle.py` also rejects empty
native archives. Eight regression tests cover missing executables, dummy DLLs,
wrong Mach-O architecture/type, truncated commands and archive inputs. Wine's
objcopy lookup now uses PATH/Homebrew or an explicit OBJCOPY override.

This is a validation repair, not a complete native build implementation. A clean
runner will now stop at the missing base Wine server archive instead of patching
an empty archive and uploading an incomplete IPA. The base server archive and
LLVM iOS source builds are still required. Local tests passed; a macOS build of
these changes has not been run.

1. Make the installable-IPA job fail on required command failures (`bash` with
   `set -euo pipefail`), retain complete build logs and per-source `.err` files,
   and require the plist-declared executable to exist and be ARM64 Mach-O before
   uploading. Keep source-only placeholder checks separate from packaging.
2. Select a compatible Xcode/SDK and replace hard-coded Homebrew tool paths with
   discovered installed tools. Compile again with complete diagnostics.
3. Resolve ntdll and win32u compilation failures from those diagnostics; require
   real, nonempty native archives. Do not cache placeholder outputs.
4. Implement the actual LLVM 15 iOS and DXMT builds described in
   `build/dxmt-ios/README.md`; the separate DXMT workflow's LLVM stage currently
   contains placeholder logic too. Validate both native archives and PE DLLs.
5. Supply genuine Microsoft runtime inputs and validate PE structure and target
   architecture. Existing fetch-script diagnostic printing is not a hard gate.
6. Build, inspect, and package the completed unsigned application. Verify the
   executable, runtime dependencies, prefix template and x64 cube resources.
7. Sign/install on the iPad, verify debugger/JIT integration and run the x64 DX11
   cube. Preserve `Documents/madeira-log.txt`, `madeira-log.prev.txt` and debugger
   logs. Only then transfer Uncrashed and attempt renderer initialization.

## Evidence downloaded in this session

- `/tmp/uncrashed-ipa-build.log`: authenticated full GitHub job log.
- `/tmp/uncrashed-artifact-audit/Madeira-unsigned.ipa`: downloaded artifact.

These temporary files may be removed by the operating system. No remote source,
workflow, release or artifact was modified during this audit.

## Installation-guide corrections

The existing `docs/SIDESTORE_IPA.md` predates this artifact inspection and must not
be treated as proof the current artifact can install or run. Current SideStore
documentation uses iloader and LocalDevVPN and includes Linux initial setup:

- https://docs.sidestore.io/docs/installation/prerequisites
- https://docs.sidestore.io/docs/installation/install

StikDebug's iOS 26 support is app-dependent. Madeira's legacy automatic URL helper
and debugger-script behavior still need device validation. An unsigned build's
entitlement warning does not establish the eventual signed app's JIT capability:

- https://github.com/StikDebug/StikDebug
- https://github.com/StikDebug/StikJIT/blob/main/INTEGRATION.md

The repository's `devicectl` transfer script requires macOS/Xcode; it does not run
on Windows through libimobiledevice. Madeira enables document sharing, so copying
the game through Files/external storage is a candidate to verify on the device.
