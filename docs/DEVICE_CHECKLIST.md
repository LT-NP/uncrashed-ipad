# Madeira device checklist (POST_BUILD_ROADMAP §9)

Written September 11, 2026, without a completed build or device session.
Every step below is gated on the milestones in
[POST_BUILD_ROADMAP](POST_BUILD_ROADMAP.md) — this checklist makes the
repeatable workflow explicit so the first device session can follow it
verbatim, not a substitute for any demonstrated result.

Target: iPad Air 11-inch M2 (2024), A2902 Wi-Fi. Confirm the actual iPadOS
version at the session and record it in the diagnostic record below.

## Before each session

- [ ] Known-good IPA on hand: commit, GitHub run URL, file hash, validator
      output recorded (roadmap §1). One artifact per test series.
- [ ] SideStore refreshed and within its signing period. Free accounts get a
      seven-day development-signing period and three active app slots —
      SideStore + StikDebug + Madeira consume all three. Verify refresh works
      BEFORE depending on it.
      (https://docs.sidestore.io/docs/faq)
- [ ] StikDebug installed with a valid pairing file for THIS iPad. Pairing
      files are device credentials: never commit them or upload them with
      diagnostics.
- [ ] Controller decided and at hand: exact model, firmware, connection mode
      (gamepad / USB FPV radio / touchscreen), desired stick layout.

## Session start (in order)

1. [ ] Connect LocalDevVPN, open SideStore, confirm Madeira is signed.
2. [ ] Open Madeira, confirm the prefix setup finishes.
3. [ ] Enable JIT via the documented manual sequence first (roadmap §3).
      Confirm debugger attach, executable-memory tests, then repeat after a
      fresh app launch. Save debugger logs.
4. [ ] Run the **x64 DX11 cube** (roadmap §4). Confirm continuous animation
      for several minutes, landscape startup, touch alignment, fresh-launch
      repeat. Copy `Documents/madeira-log.txt`,
      `Documents/madeira-log.prev.txt` and debugger logs PROMPTLY — launches
      rotate runtime logs.
5. [ ] Only after the cube: transfer Uncrashed, verify file counts/sizes
      (roadmap §5), then launch with
      `Uncrashed -dx11 -windowed -ResX=1024 -ResY=768 -log` (roadmap §6).
6. [ ] Flight controls: open the in-app gamepad diagnostics (gamecontroller
      toolbar button, roadmap §7 step 2). Confirm four proportional axes move,
      then calibrate inside Uncrashed with simultaneous — not one-at-a-time —
      stick movement.
7. [ ] Back up saves, configuration and controller mappings
      (`madeira-controls.json`, `madeira-gamepad.json`) before changing the
      app identity, removing the app, or replacing the prefix.

## After OS / debugger / app updates

- [ ] Revalidate the launch → JIT → cube sequence from scratch.
- [ ] Keep the known-working IPA, commit, debugger version, device OS version
      and these instructions together.
- [ ] Test updating the app in place: configuration and saves must survive.

## Diagnostic record (copy per test, cf. roadmap §9)

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

## What still needs a device to answer

JIT behavior on the exact iPadOS version, Wine/DXMT/Steam compatibility for
Uncrashed, the analog-controller path end to end (the Wine-side hook is
pending §6 evidence by design), and sustained performance within the memory
budget. The most useful first session stays small: install, prove JIT, render
the x64 cube, export logs.
