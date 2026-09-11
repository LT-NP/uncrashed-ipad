# Installing a verified Madeira IPA

The September 10 artifact from run `34445071135` is incomplete: it has no app
executable. Do not use that artifact for installation. See
[the build audit](BUILD_AUDIT_2026-09-10.md). The corrected workflow must finish
compiling and pass bundle validation before the following device steps apply.

## Initial SideStore setup

Current official instructions use iloader and LocalDevVPN and support initial
setup from Linux, Windows or macOS:

- [Prerequisites](https://docs.sidestore.io/docs/installation/prerequisites)
- [Installation](https://docs.sidestore.io/docs/installation/install)

Install LocalDevVPN on the iPad. Install iloader and the platform prerequisites
on the computer, connect the unlocked iPad by USB, trust the computer and use
iloader to install SideStore. Follow the iPadOS 26 instructions to trust the
signing account and enable Developer Mode. Connect LocalDevVPN, sign in to
SideStore and refresh SideStore itself before installing other apps.

## Install and validate the app

1. Download `Madeira-unsigned-ipa` from a completed build that passed the new
   bundle-validation steps. Extract the outer artifact ZIP to obtain the IPA.
2. Transfer the IPA to Files on the iPad. With LocalDevVPN connected, select it
   using SideStore's My Apps / + flow to sign and install it.
3. Install and configure [StikDebug](https://github.com/StikDebug/StikDebug),
   including a valid pairing file for this iPad. Its iOS 26 support depends on
   the target app. The signed app must support debugger attachment; merely
   listing entitlements in an unsigned project's source does not prove this.
4. Open Madeira and validate JIT, then run **x64 DX11 cube**. Preserve debugger
   logs and Madeira Documents files `madeira-log.txt` and `madeira-log.prev.txt`.
   A rendered, running cube is the first graphics milestone.

Madeira's automatic helper currently uses a legacy URL scheme and embeds a
custom debugger script. Its behavior needs testing against the current
[StikDebug integration](https://github.com/StikDebug/StikJIT/blob/main/INTEGRATION.md).
Do not interpret a JIT badge alone as proof that the full Wine/FEX runtime works.
Do not arbitrarily detach the debugger or change the memory pool to mask errors.

## Transfer and launch Uncrashed

After the cube works, copy the full owned game installation (roughly 20 GB) to:

```
Documents/wine/drive_c/Program Files/Uncrashed FPV Drone Sim/
```

The shipping executable relative to that directory is:

```
Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe
```

The app enables document sharing. Files / On My iPad / Madeira with external
storage is a transfer route to verify on the device. The existing scripted
fallback uses macOS and Xcode, after Madeira initializes its Wine prefix:

```sh
xcrun devicectl list devices
bash scripts/deploy-uncrashed.sh "/path/to/Uncrashed FPV Drone Sim" DEVICE_ID INSTALLED_BUNDLE_ID
```

`devicectl` does not run on Windows through libimobiledevice.

Enable JIT for the app session, then select **Uncrashed (UE4, DirectX 11)**.
The default arguments are `Uncrashed -dx11 -windowed -ResX=1024 -ResY=768 -log`
(1024x768 matches the Wine monitor and touch mapping).
`Documents/uncrashed-args.txt` overrides the entire argument string.
Save Madeira, debugger and any Unreal `Saved/Logs` output. The first target is a
splash or renderer initialization, followed by stable gameplay and controls;
Uncrashed compatibility has not been demonstrated.

Refresh the sideloaded apps before their signatures expire. A free account's
three active app slots accommodate SideStore, StikDebug and Madeira. See the
[SideStore FAQ](https://docs.sidestore.io/docs/faq) for refresh behavior and limits.

The repeatable session workflow (JIT order, cube-first rule, log rotation,
controller diagnostics, transfer verification) is kept as a checklist in
[DEVICE_CHECKLIST](DEVICE_CHECKLIST.md).
