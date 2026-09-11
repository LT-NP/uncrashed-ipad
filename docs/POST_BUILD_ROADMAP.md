# Uncrashed on iPad: work remaining after the build

Written September 11, 2026. This is a proposed execution plan, not a report of completed device tests. No installation, debugger setup, game transfer or device test described below was performed while writing it. Since then, the build-independent app-side work has been implemented without device validation — §3 protocol comparison with URL migration, §7 controller state/diagnostics/defaults, §9 device checklist, §5 transfer tooling (see status notes under those sections). All device milestones below are unchanged.

Target recorded in this project: iPad Air 11-inch M2 (2024), A2902 Wi-Fi, iPadOS 26.5.2. Confirm the actual OS version at the first device session. The intended approach runs the Windows game locally through Madeira, Wine, FEX and DXMT; GitHub supplies the compiled app. It does not run the game remotely or stream video to the iPad.

A successful build is only the entry condition. There is no demonstrated Uncrashed gameplay on this iPad yet, and no reliable completion date or frame-rate estimate.

## Milestones and ownership

| Order | Milestone | Who/where | Evidence needed |
|---|---|---|---|
| 1 | Accept a complete IPA | Developer/computer | Validated executable and runtime resources, recorded commit and artifact hash |
| 2 | Sign, install and open Madeira | User/iPad and initial computer setup | App opens and its Documents folder is accessible |
| 3 | Establish working JIT | User/iPad; developer diagnoses logs | Generated code actually executes, including after a fresh app launch |
| 4 | Validate Wine/FEX/graphics | User/iPad | x64 DX11 cube renders continuously |
| 5 | Transfer the complete owned game | User/computer or external storage | Expected executable and game assets exist in the correct app container |
| 6 | Reach Uncrashed's menu and a map | User/iPad; developer fixes observed failures | Menu, level loading and a rendered scene |
| 7 | Implement/verify flight controls | Developer plus user's exact controller | Four independent analog axes reach the game and calibrate correctly |
| 8 | Reach sustained, usable flight | User/iPad; developer tunes | Repeatable flight with acceptable frame pacing, input response and stability |
| 9 | Make everyday use repeatable | User/iPad; developer documents | Relaunch, signing refresh and updates preserve working setup and saves |

Device work requires you or someone with physical access to the iPad. Code fixes can be developed on Linux and compiled on GitHub. A Mac is needed for the existing `devicectl` transfer fallback, but the proposed initial signing route supports other desktop platforms.

## 1. Accept the artifact and prepare a test record

Before installing, download the artifact from a successful full IPA workflow. Extract the outer GitHub artifact ZIP to obtain `Madeira-unsigned.ipa`. Do not confuse the dedicated DXMT libraries artifact with an installable application.

Record the commit, run URL, IPA hash and validator output. The app must contain its plist-declared ARM64 executable, real Wine/DXMT dependencies, Microsoft runtime inputs, prefix template and cube resources. The project's structural validator helps catch incomplete packaging; it cannot prove runtime compatibility.

Keep a copy of the accepted IPA and logs outside temporary GitHub artifact storage. Use one known artifact for a device test series, so results can be attributed to a specific version.

**Completion:** a traceable IPA that passed package checks. The historical green run documented in [the build audit](BUILD_AUDIT_2026-09-10.md) failed this requirement.

## 2. Sign and install the app

The hosted workflow produces an unsigned app. It still needs signing for the iPad before installation.

The planned route is SideStore. Its official setup uses iloader on a computer, a USB connection and device trust, then LocalDevVPN and SideStore on the device. Follow the platform-specific prerequisites and the iPadOS instructions for account trust and Developer Mode. Refresh SideStore after its initial setup, then import the Madeira IPA for signing and installation. Linux and Windows are supported initial-setup routes. See [prerequisites](https://docs.sidestore.io/docs/installation/prerequisites) and [installation](https://docs.sidestore.io/docs/installation/install).

Record the resulting app identity and signing method. Confirm Madeira opens, the initial prefix setup finishes, and its document-sharing folder can be accessed. If installation fails, retain the exact error before retrying. If it opens and immediately exits, collect the device crash report; this is a different failure from signing rejection.

Debugger attachment must work with the final signed app. Entitlements listed in project source or an unsigned IPA do not establish that capability after signing.

**Completion:** Madeira opens reliably and exposes its files. This does not yet prove JIT or Windows execution.

## 3. Establish JIT on this exact iPad

FEX translates Windows x64 code into ARM64 code at runtime. The resulting code must be executable under the device's JIT/debugger setup.

Prepare StikDebug and the pairing material required by its current instructions. Pairing files are device credentials: keep them out of GitHub and diagnostic uploads. Verify that the debugger attaches to the running Madeira process and that Madeira's executable-memory tests succeed. Repeat after closing and reopening the app.

The repository includes an automatic helper using a legacy URL scheme and custom debugger behavior. Compare it with the current integration protocol before relying on automatic activation. First establish a working manual sequence; then, if needed, update the helper and failure messages. Current upstream documentation treats iOS 26 JIT compatibility and app integration as distinct requirements. Generic StikDebug support does not demonstrate Madeira compatibility on this exact OS. See [StikDebug](https://github.com/StikDebug/StikDebug) and its [integration guide](https://github.com/StikDebug/StikJIT/blob/main/INTEGRATION.md).

Status (Sept 11, 2026, no device): the comparison was done against the integration guide. Part 1 (breakpoint protocol) matches the allocator's structure; Part 2 closed two gaps — the helper now prefers `stikdebug://enable-jit` with bundle-id + pid + base64 script-data (correct variant for a custom script) and keeps the legacy `stikjit://` URL as byte-identical fallback. TXM-conditional script omission needs framework TXM detection and was deliberately not changed. Device validation still required.

Do not treat a JIT badge or successful debugger request as the final test. Generated instructions must execute, and the translated runtime must remain stable. Follow the verified attachment lifecycle rather than assuming it is safe to detach the debugger or suspend its app.

**Possible development:** debugger protocol integration, JIT memory handling, startup sequencing and actionable error reporting.

**Completion:** repeatable code execution with a documented launch sequence and saved logs.

## 4. Validate the runtime with the cube

Initialize the Wine prefix, then run Madeira's **x64 DX11 cube**. This exercises x64 translation, Windows loading and D3D11-to-Metal rendering without the complexity of Uncrashed's large installation.

Confirm the cube animates for several minutes. Test landscape startup, touch alignment, returning to the launcher if supported, and a fresh app launch. The **arm64 DX11 cube** can help isolate a translation-specific failure: if ARM64 renders but x64 does not, investigate the additional x64/FEX path. This comparison narrows the investigation; it does not prove which component is broken.

Save `Documents/madeira-log.txt`, `Documents/madeira-log.prev.txt`, debugger logs and any device crash report. Copy them promptly because subsequent launches rotate runtime logs.

**Possible development:** Wine startup, missing runtime exports, FEX execution, Metal shader compilation, swapchain presentation or device-specific JIT faults.

**Completion:** a continuously rendered x64 cube. A static app window or successful ARM64-only test is insufficient.

## 5. Transfer the complete game

Use your owned Windows installation. The audited copy contains 33 pak files and approximately 20.44 GB of files (19.04 GiB). Those numbers describe the inspected version, not every future update. Allow additional storage for the runtime, saves, caches and transfer staging; the existing transfer script asks for at least 25 GiB free, which is a starting estimate rather than a guaranteed ceiling.

The expected destination inside Madeira is:

```text
Documents/wine/drive_c/Program Files/Uncrashed FPV Drone Sim/
```

The executable beneath that directory must be:

```text
Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe
```

Copy the entire installation, preserving relative paths, pak files, supporting DLLs and Steam files. Avoid accidentally introducing a second nested `Uncrashed FPV Drone Sim` directory.

The candidate route without a Mac is Files/external storage into Madeira's shared Documents folder. Its reliability for this large copy still needs device testing. The existing fallback is [deploy-uncrashed.sh](../scripts/deploy-uncrashed.sh), which requires macOS/Xcode and an initialized app container. It is not a Windows `libimobiledevice` command.

Compare file counts and total sizes after transfer, and checksums where practical. An existing executable alone does not prove the transfer completed.

Tooling (no device needed): `tools/audit-uncrashed.py --manifest` writes a per-file manifest (sizes always, sha256 for smaller files or `--hash-all`) at the source; `tools/verify-uncrashed-transfer.py --manifest --dest` checks presence, sizes, hashes, the shipping-executable path and the nested-duplicate-directory mistake. Both are covered by `tools/test_verify_transfer.py`.

**Completion:** the launcher finds the shipping executable and all assets are present in the correct container.

## 6. Launch Uncrashed and resolve the first failure

Use the existing **Uncrashed (UE4, DirectX 11)** entry with its initial arguments:

```text
Uncrashed -dx11 -windowed -ResX=1024 -ResY=768 -log
```

The 1024×768 starting point matches the current monitor, rendering area and touch mapping. `Documents/uncrashed-args.txt` replaces the complete argument string; retain required arguments when experimenting.

Work through these checkpoints in order: executable loads, renderer initializes, splash/menu appears, a map loads, a scene renders, then flight starts. Preserve the first error and the last successful checkpoint. Shipping Unreal builds may not produce useful game logs even with `-log`; use Madeira and device diagnostics too.

| Observed failure | Investigation |
|---|---|
| Missing module or imported function | Identify the exact DLL/export and architecture; repair packaging or the relevant runtime implementation |
| Steam initialization or ownership error | Determine the game's supported Steam requirements and whether the runtime can satisfy them with legitimate Steam components |
| Shader error, black scene or broken effects | Capture DXMT/Metal diagnostics and isolate the failing shader or graphics feature |
| App disappears while loading | Distinguish a crash from OS memory termination using device reports |
| Menu works but map loading stalls | Check complete assets, storage, memory use and the last Unreal/runtime activity |
| Scene renders but controls do nothing | Investigate the input path described below |

A working Steam route may be a substantial separate compatibility problem. Do not assume direct launching eliminates it. No Steam bypass or replacement is part of this plan.

**Completion:** an actual loaded game scene, with enough evidence to reproduce startup.

## 7. Make flight controls work

This was a concrete implementation gap in the app: touchscreen stick directions generated keyboard presses, and `.pad` actions did nothing. The app-side half has since been implemented without device validation — `GamepadBridge` (`app/Madeira/GamepadBridge.swift`) merges physical GameController input with proportional touchscreen sticks into a `winios` pad store (`winios_pad_update`/`winios_pad_get_state` in `app/Madeira/Winios/`), with a diagnostics view, first-launch flight layout, calibration persistence and interruption release. What remains is the Wine-side hook into the input API the game actually uses, plus device validation of every step below.

First identify your intended device: a conventional gamepad, an FPV radio connected by USB, or touchscreen controls. Record its exact model, firmware, connection mode and desired stick layout. Recognition by iPadOS or another simulator does not establish that Wine or Uncrashed receives it.

Proposed development sequence:

1. Confirm the iPad app can receive the physical controller's events. For a radio, first establish whether its USB/HID mode is accessible through the available iPadOS APIs. (App side ready: `GamepadBridge.start()` observes `GCController` and the diagnostics view shows raw axes. A RadioMaster in USB joystick mode is the expected-good case.)
2. Build a diagnostic display showing raw axis values, buttons and connection state. (Implemented: gamecontroller toolbar button → `GamepadDiagnosticsView`, with deadzone/invert/throttle-latch calibration.)
3. Implement the appropriate bridge into the Windows input API used by the game. Determine from runtime evidence whether XInput, SDL joystick handling, another Wine HID path, or a combination is required. (Not started by design: the `winios_pad_get_state` store is the source the hook will read, so the hook cannot pick the wrong consumer before §6 evidence exists.)
4. Expose four independent proportional axes: throttle, yaw, pitch and roll. Configure full ranges, inversion, centering, dead zones and throttle behavior. (App side ready: merged LX/LY/RX/RY with deadzone/invert/scale calibration and throttle latch; Uncrashed-side mapping still needs the device.)
5. Calibrate inside Uncrashed and verify simultaneous axis movement rather than testing one stick direction at a time.
6. Add reset/restart, pause, menu selection and back actions so a session is usable without a desktop keyboard. (App side ready: first-launch layout ships Menu/View/A/B; game-side bindings still need the device.)
7. Test disconnect/reconnect and app interruptions, ensuring stale input is released. (App side ready: `winios_release_all_inputs` + virtual release on resign-active; device test still needed.)

If touchscreen flight is desired, it needs a real analog implementation, suitable throttle behavior and simultaneous multi-touch. Keyboard-emulating sticks can help navigation, but they do not complete that work.

**Completion:** the game sees correct continuous movement on all four axes, calibration persists, and the intended controller supports actual flight.

## 8. Tune performance and test stability

Start from a reproducible map and conservative settings. Change one variable at a time: resolution, shadows, post-processing, texture quality or other available game options. Record the exact settings alongside results.

Measure average frame rate where available, frame-time spikes, loading time, input response and stability as the iPad warms. Compare initial shader-compilation stutters with a second pass through the same scene. Record memory-related terminations separately from low frame rate.

Lower resolution primarily reduces rendering work. It may not resolve CPU translation overhead, shader compatibility, JIT faults or memory pressure. Coordinate resolution changes with display geometry and touch mapping.

Proposed acceptance sequence: a short launch-and-flight test, a 10-minute repeatable flight, then a 30-minute session and a second map. Agree a minimum acceptable frame rate and input response with you after observing the baseline. No specific performance level is established yet.

Also check audio, save/settings persistence, rotation, returning from interruptions and relaunching after a crash.

**Completion:** repeatable flight at an agreed quality and responsiveness level without persistent rendering faults or unexplained termination.

## 9. Establish the everyday workflow

Write a short device-specific checklist: signing/refresh state, JIT activation, Madeira launch, Uncrashed launch and log export when something fails. Verify it after a device reboot and after an app update.

With a free Apple account, SideStore documents a seven-day development-signing period and a three-active-app limit including SideStore. SideStore, StikDebug and Madeira therefore consume the three slots if all are installed through that route. Verify refreshing works before depending on it; this is distinct from recompiling the app. See the [SideStore FAQ](https://docs.sidestore.io/docs/faq).

Back up saves, configuration and controller mappings before changing the app identity, removing the app or replacing the prefix. Determine the game's actual save locations from the working installation rather than assuming everything is inside the game folder. Test updating the same app while retaining its data.

Keep the known-working IPA, commit, debugger version, device OS version and instructions together. Revalidate the launch/JIT sequence after OS or debugger updates.

**Completion:** you can start another session, refresh signing and update the app without losing configuration or needing another development session each time.

## Diagnostic record for each test

```text
Date and test ID:
IPA commit / GitHub run / file hash:
iPad model and OS:
Signing method and app identity:
Debugger version and activation method:
Game version and transfer verification:
Controller model / mode / connection:
Launch arguments and graphics settings:
Last successful milestone:
Exact failure and reproduction steps:
Time to failure / session duration:
Attached runtime, debugger and device logs:
One change proposed for the next test:
```

## What could remain blocked even with a perfect build?

The largest unresolved questions are JIT behavior on this exact iPadOS version, Uncrashed-specific Wine/DXMT and Steam compatibility, an accessible analog-controller path, and sustained performance within the app's usable memory budget. Some may require substantial runtime development. Successful compilation does not settle them.

The most useful first device session is therefore small: install Madeira, prove JIT, render the x64 cube and export logs. Once those work, transfer the game and investigate its actual behavior. Controller feasibility can be explored independently, but it is part of the definition of playable flight.
