# Sideload Madeira IPA via SideStore (no Mac per week)

This guide is for the hosted `macos-15` IPA (`Madeira-unsigned.ipa` from GH `fix/ci-ios-build`).

**Prerequisites (once):**
- Windows PC + iPhone/iPad on same WiFi, Apple ID (free = 7-day, 3 apps).
- Install SideStore: https://docs.sidestore.io/docs/getting-started/ — pair via `SideServer` + `WireGuard` VPN (StikDebug JIT also uses loopback, so VPN must be off during JIT detach).

**Weekly IPA install (GH bypasses friend's Mac):**
1. GH `Actions` → `fix/ci-ios-build` → latest green `Build IPA (hosted, unsigned)` → download `Madeira-unsigned-ipa` (contains `Payload/Madeira.app`).
2. SideStore → `My Apps` → `+` → select `Madeira-unsigned.ipa` → sign with your Apple ID (preserves `get-task-allow`+`allow-jit` `app/Madeira/Madeira.entitlements:7`). Free profile expires in 7 days — SideStore refreshes on-device without a Mac.
3. Trust profile: `Settings → General → VPN & Device Management`.

**First launch on iPad Air M2 26.5.2:**
- Open Madeira → check `JIT` badge `ContentView.swift:850` — `StikDebug` must be installed, open `stikjit://enable-jit?bundle-id=...` URL (see `StikJITHelper.swift:32`), `CS_DEBUGGED` via `JITAllocator.c:424` `csops`.
- Enable JIT → allocate `896MB` pool `StikJITHelper.swift:252` `vm_remap` + detach.
- Test DX11 cube `x64 DX11 cube` button before Uncrashed — should show spinning cube via `build/d3d11-triangle`.

**Deploy Uncrashed (20GB, after JIT + cube ok):**
- On your Mac (friend's, once): `bash scripts/deploy-uncrashed.sh "/path/to/Uncrashed FPV Drone Sim" DEVICE_ID BUNDLE_ID` (`xcrun devicectl` `appDataContainer` `Documents/wine/drive_c/Program Files/Uncrashed FPV Drone Sim`).
- Or via `devicectl` from Windows with `libimobiledevice` if available.
- Launch `Uncrashed (UE4, DirectX 11)` `ContentView.swift:1468` (`-dx11 -windowed -ResX=960 -ResY=540 -log` or `Documents/uncrashed-args.txt` override). First win is splash/renderer init, not gameplay — save `LogStore` + `Saved/Logs`.

**Troubleshooting:**
- `JIT` badge red → `StikDebug` not attached, reinstall `StikDebug` via SideStore, retry URL.
- `VCRuntime` missing → `tools/fetch-vcruntime.sh` locally (GH dummy `MZ` 15 bytes won't run).
- `Jetsam` `phys_footprint` → `JITAllocator.c:227` `NO_FOOTPRINT` not applied, reduce `896MB` pool or close apps.
