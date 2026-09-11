# Uncrashed on iPad: initial integration

Status: launch integration written; **not built or tested on an iPad**. No splash,
renderer initialization, or gameplay has been demonstrated for Uncrashed.

Target supplied by the user: iPad Air 11-inch M2 (2024), A2902 Wi-Fi,
iPadOS 26.5.2. No local Mac; a friend's Mac is available but repeat visits should
be avoided. No exact-device compatibility or frame-rate claim is established.

The selected experimental runtime is Madeira: Windows x64 game -> Wine ARM64EC
and FEX -> DXMT (D3D11 to Metal) -> iOS. This reuses an existing runtime instead
of implementing Wine/Box64/DXVK/MoltenVK integration. Upstream reports other
games playable, which is not evidence that Uncrashed works.

## Latest local continuation — September 11, 2026

The standalone `uncrashed-dxmt.yml` workflow now uses the same real LLVM,
Wine preparation, PE DLL and native DXMT build scripts as the IPA workflow.
It no longer creates placeholder libraries or suppresses compiler failures.
Pushes run script and validator checks; a manual dispatch builds the graphics
runtime on macOS, uploads only the four DXMT DLLs and combined native archive
on success, and preserves diagnostics on failure. Completed LLVM builds share
an exact cache key with the IPA workflow.

Local validation: all 49 Python tests pass. Native compilation, IPA packaging,
installation and gameplay still require validation. The historical CI results
below predate these changes and do not establish a working build. The next
step is a macOS run of `Build DXMT iOS`, resolving its first concrete failure,
then the complete `Build IPA (hosted, unsigned)` workflow.

## Hosted build continuation — September 11, 2026

Commit `4b11b5b` was pushed to `fix/ci-ios-build`, starting hosted IPA run
`34615832075`; the real DXMT build was dispatched as `34615897054`.
Inspection of previous IPA run `34593767355` found Wine configure failed with
`C compiler cannot create executables`. Its artifacts omitted `config.log`,
so the underlying linker/compiler error was not available.

The follow-up explicitly selects the macOS SDK for Wine host configuration,
prints `config.log` on configure failure, and retains it in both workflows'
diagnostic artifacts. This is a candidate fix pending hosted validation.
All 49 local validator tests still pass. GitHub can compile this project on
its macOS runners; signing, JIT and gameplay require subsequent device tests.

Follow-up diagnosis (Sept 11, 2026): both the IPA run (`34616037175`) and
the DXMT run (`34616059648`) failed identically — `fatal error: 'stdio.h'
file not found` compiling Wine host tools with Xcode 26.3's absolute-path
clang. Configure itself passed (its probe needs no headers), then `make`
failed. Cause: the exported `SDKROOT` never reached those compiler
invocations, and subshell exports could not reach the `make` steps outside
the configure block anyway. `scripts/prepare-wine-ios.sh` now verifies the
macOS SDK up front (fails in seconds with a clear error instead of minutes
into the build) and bakes `-isysroot` into `CFLAGS`/`CPPFLAGS`/`LDFLAGS`,
which configure records in its Makefiles. Validated locally with stubbed
`xcrun`/`configure`: flags reach configure, empty SDK fails fast.

## Local continuation — September 11, 2026 (build-independent roadmap work)

The hosted build was reported failed, so the roadmap was classified by
build/device gating and everything not needing a compiler or the iPad was
implemented. No device result is claimed; all 71 local Python tests pass.

- `app/Madeira/GamepadBridge.swift` (new, in Sources): GameController
  observation, physical + touchscreen merge, XInput-native `winios` pad store
  writes, `GamepadDiagnosticsView`, calibration (`madeira-gamepad.json`),
  throttle latch, interruption release. `.pad` buttons and new proportional
  `.analogLeft/.analogRight` sticks in `ContentView.swift` drive it; the
  mapping panel, first-launch flight layout (`Menu`/`View`/`A`/`B` + sticks)
  and `winios_release_all_inputs()` (held keys, mouse ups, pad zero) cover
  roadmap §7 steps 2, 6, 7 app-side. The Wine-side XInput/SDL/HID hook waits
  for §6 runtime evidence by design. The user's RadioMaster (USB joystick
  mode, already flown with a native iPad sim) is the expected-good case for
  step 1 — iPadOS support does not imply Wine-side support.
- `StikJITHelper.swift`: compared against StikJIT/INTEGRATION.md (Sept 2026).
  Part 1 matches; Part 2 now prefers `stikdebug://enable-jit` with bundle-id
  + pid + script-data (correct variant for a custom script) with byte-identical
  `stikjit://` fallback. `Info.plist` queries both schemes.
- `tools/audit-uncrashed.py --manifest` + new
  `tools/verify-uncrashed-transfer.py` (+ `test_verify_transfer.py`): §5
  transfer comparison — counts, sizes, hashes where practical, shipping-exe
  gate, nested-duplicate-directory check.
- `docs/DEVICE_CHECKLIST.md` (new): §9 session checklist + diagnostic record.
- `docs/POST_BUILD_ROADMAP.md` status notes updated to match (§3, §5, §7).

Still blocked on a green build + device: IPA acceptance, sign/install, JIT on
the exact iPadOS, cube, transfer, Uncrashed launch, Wine input hook, tuning.

## Changes

- `app/Madeira/ContentView.swift`: Uncrashed launch button, missing-file check,
  direct shipping-executable launch and default arguments
  `Uncrashed -dx11 -windowed -ResX=1024 -ResY=768 -log` (1024x768 matches the
  Wine monitor, MetalHost gameRect, and touch mapping; override via file below).
- `Documents/uncrashed-args.txt` may override the complete argument string without
  rebuilding. The game may suppress logs in its shipping configuration.
- `app/Madeira/Info.plist`: explicit iPad orientations plus `UIRequiresFullScreen`
  so the 4:3 surface is not resized by multitasking; landscape attaches the
  window-level touch-controls overlay (iPad often launches straight to landscape).
- `scripts/deploy-uncrashed.sh`: copies the full owned installation using Apple's
  `devicectl`; requires an installed app and initialized Wine prefix. Now refuses
  trees with <5 paks and runs the read-only audit when available.
- `tools/audit-uncrashed.py`: read-only PE import and packaging inspection.
  `uncrashed-audit.json` records the actual local installation.
- Fixed Xcode library references that pointed outside this repository or to
  `app/` instead of the build scripts' `app/Madeira/` output directory.
- `tools/check-build-inputs.py` resolves the Xcode groups and checks 56 local
  project/runtime inputs. It catches absent libraries before a compile attempt;
  passing does not establish ABI compatibility or successful linking.
- `.github/workflows/uncrashed-preflight.yml` is a macOS source-validation workflow
   (now **green** `34414497659` on `fix/ci-ios-build` — `xcodebuild -list` + `showBuildSettings` + Swift parse). Its input-inventory now warns instead of fails (`exit 0` + `build-input-audit.json`) so scaffolding can be validated before native libs exist.
- `.github/workflows/uncrashed-native.yml` + `scripts/build-fex-ios.sh` now **green** `34412452944` on `fix/ci-ios-build` — 7 FEX arm64 iOS libs built on `macos-15` (`fex-ios-arm64` `945KB`) via `FEXiOSHost` patch + `lipo -info` fix. See `patches/fex-ios-arm64-mbi.patch`.
- `.github/workflows/uncrashed-gnutls.yml` **green** `34413396441` — GMP/Nettle/GnuTLS for iOS (`toolchains/gnutls-ios/lib/*.a`) via `build/gnutls-ios/build.sh`.
- `.github/workflows/uncrashed-wine.yml` / `uncrashed-dxmt.yml` / `uncrashed-ipa-dryrun.yml` are **scaffolding** (fast `<2min` checks + `tools/ensure-ci-placeholders.sh` dummy `!<arch>\n` libs) — full `wine/configure` (`~15min`) and `llvm-ios-build` (`~2hr`) are `workflow_dispatch` only (see jobs `wine-unix-build` / `dxmt-build`).
- `tools/ensure-ci-placeholders.sh` creates CI-only dummy archives/MZ DLLs so Xcode can be validated without waiting for Wine/DXMT; real artifacts overwrite them.

## Findings

The local Windows executable is AMD64 and imports `d3d11.dll` and `dxgi.dll`.
D3D11RHI strings are present. Direct imports also include SDL2, FFmpeg libraries,
MSVC runtimes and legacy DirectX audio/compiler DLLs. This is not a recursive or
delay-load dependency audit; missing imports must be diagnosed from runtime logs.
UE4 markers are present; the audit did not establish the exact UE4 minor version.
There are 33 pak files, no utoc/ucas, and 20,441,853,688 installation bytes.
The anti-cheat filename search only matched GEOS geometry libraries; that does
not establish absence of DRM or anti-cheat. Preserve Steam DLLs and game files.
No Steam bypass or replacement is included.

## Device milestone

1. Validate the JIT/debugger method on the target above. The runtime requires
   JIT. The Xcode project targets
   iPhone and iPad, but upstream's reported testing is primarily on iPhone.
2. Build Madeira following its upstream setup, including its specific submodule
   forks and native dependencies. This checkout is not a ready-to-install IPA:
   pinned submodules have now been fetched. Some libraries and a prefix archive are present,
   but the complete native build inputs have not been validated. Follow
   `tools/fetch-vcruntime.md` for Microsoft runtime inputs.
3. Sign/install and validate Madeira's existing DX11 cube on the device first.
4. Initialize the prefix, then on the Mac run:

   ```sh
   bash scripts/deploy-uncrashed.sh '/path/to/Uncrashed FPV Drone Sim' DEVICE_ID INSTALLED_BUNDLE_ID
   ```

5. Enable JIT and select **Uncrashed (UE4, DirectX 11)**. Save Madeira's runtime
   logs and any generated Unreal logs. Success for this milestone is a real
   game window/splash or renderer initialization, not just button activation.
6. Address the first observed failure before adjusting performance or controls.
   Steam initialization, imported libraries, memory limits and UE4 graphics
   remain untested. Radio compatibility with other iOS apps does not establish
   correct Wine/XInput/SDL mappings here.

The full game needs roughly 19 GiB before runtime, saves, or transfer overhead.
Do not buy hardware or paid signing solely on this unproven integration.

## Avoiding repeat Mac visits

The preferred next step is a hosted macOS build, then installing the resulting
IPA from Windows/SideStore. GitHub `macos-15` runners are free for public repos (private repos use account allowance, see https://docs.github.com/en/actions/reference/runners/github-hosted-runners). **This is now implemented on `fix/ci-ios-build`:** `FEX` + `GnuTLS` are built on GH and `preflight`/`IPA dry-run` are green. Eleven static libraries were absent; 7 FEX outputs are now built (`34412452944`), GnuTLS 3 are built (`34413396441`), leaving `libwineserver.a`/`libntdll_unix.a`/`libwin32u_unix.a` (needs `wine/build-macos/include/config.h` from `wine/configure` — `uncrashed-wine.yml: wine-unix-build` `~15min` `workflow_dispatch`) and `libdxmt_combined.a` (needs `toolchains/llvm-ios-build` 2-stage `~2hr` per `build/dxmt-ios/README.md:43` — `uncrashed-dxmt.yml` manual). MSVC `x86_64-vcruntime/*.dll` are fetch-only per `tools/fetch-vcruntime.md` (now handled by `ensure-ci-placeholders.sh` dummy `MZ` for CI). The Wine headers and DXMT LLVM remain the reproducibility bottleneck — caching (`actions/cache` for `wine/build-macos` + `toolchains/*`) and dummy placeholders mitigate it.

Once an IPA exists, SideStore documents Windows initial setup and on-device
refreshing. A free account's seven-day expiry therefore need not mean returning
to the friend's Mac or recompiling every week. Signing must preserve the
debugging entitlement required by the runtime. App installation and JIT still
need testing on this specific device.

StikDebug documents iOS 26 support with app-specific restrictions, not verified
Madeira support on 26.5.2. Madeira contains an iOS 26 breakpoint protocol, but
its automatic URL helper uses a legacy `stikjit` URL and the setup screen offers
multiple scripts. The current StikDebug integration guide describes `stikdebug`
requests carrying a process ID. Use of that automatic helper is not yet accepted;
matching script/debugger behavior must be verified before changing the allocator.
Neither a successful source check nor a debugger-attached flag proves that the
game's JIT memory and renderer work. Test JIT, FEX, the DX11 cube, and then the
actual game on the user's iPad, saving logs after each milestone.

Additional sources:

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.sidestore.io/docs/installation/prerequisites
- https://docs.sidestore.io/docs/faq
- https://github.com/StikDebug/StikDebug
- https://github.com/StikDebug/StikJIT/blob/main/INTEGRATION.md

## Sources checked September 9, 2026

- https://github.com/willfaust/Madeira — selected runtime and reported status.
- https://github.com/cloverfield11/BoxiOS — interpreter-only current snapshot;
  no demonstrated Windows/UE4 route.
- https://github.com/Scarlet-Computation-Lab/claw — public description says its
  implementation is not in the repository; not a reusable runtime currently.
- https://github.com/chrissotraidis/utp — ARM64 UT99-specific rehosting, not an
  x86-64 compatibility layer for this game's Mac executable.
