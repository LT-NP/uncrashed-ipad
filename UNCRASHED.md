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

## Changes

- `app/Madeira/ContentView.swift`: Uncrashed launch button, missing-file check,
  direct shipping-executable launch and default arguments
  `Uncrashed -dx11 -windowed -ResX=960 -ResY=540 -log`.
- `Documents/uncrashed-args.txt` may override the complete argument string without
  rebuilding. The game may suppress logs in its shipping configuration.
- `scripts/deploy-uncrashed.sh`: copies the full owned installation using Apple's
  `devicectl`; requires an installed app and initialized Wine prefix.
- `tools/audit-uncrashed.py`: read-only PE import and packaging inspection.
  `uncrashed-audit.json` records the actual local installation.
- Fixed Xcode library references that pointed outside this repository or to
  `app/` instead of the build scripts' `app/Madeira/` output directory.
- `tools/check-build-inputs.py` resolves the Xcode groups and checks 56 local
  project/runtime inputs. It catches absent libraries before a compile attempt;
  passing does not establish ABI compatibility or successful linking.
- `.github/workflows/uncrashed-preflight.yml` is a manually triggered macOS
  source-validation workflow. It has **not run remotely** and does not build an
  IPA. Its input-inventory step currently fails until dependencies are built.
- `.github/workflows/uncrashed-native.yml` and `scripts/build-fex-ios.sh` start
  the native build work with the pinned FEX fork's seven arm64 iOS libraries.
  This first dependency build is not a complete app build and has not run yet.

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
IPA from Windows/SideStore. GitHub documents free standard macOS runners for
public repositories; private repositories use the account's allowance and may
incur charges. No repository has been published and no workflow has been run.
The checked-in workflow is only the first source/input check, not a complete
native dependency bootstrap. Eleven static libraries are still absent (seven
FEX outputs and four Wine/graphics outputs), along with the MSVC input folder.
The Wine build scripts also require generated Wine headers, and DXMT requires
an iOS LLVM build. Those prerequisites need a reproducible Mac build recipe.

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
