import Foundation
import SwiftUI
import UIKit
import GameController
import Combine

// POST_BUILD_ROADMAP §7 — virtual gamepad bridge.
//
// Status: APP-SIDE STATE ONLY. No Wine/XInput hook reads this yet.
//
// Why this shape: the roadmap's step 3 requires runtime evidence (from the
// first Uncrashed launch, §6) to decide whether the game needs XInput, SDL
// joystick handling, another Wine HID path, or a combination. That evidence
// does not exist — no build, no device session — so wiring a full virtual HID
// device now would be guessing at the consumer. Instead this file is the
// single source of truth both future consumers will read:
//
//   physical GCController ─┐
//                          ├─ merge ─▶ winios_pad_update (Winios.m store)
//   touchscreen sticks/buttons ─┘              ▲
//                          future Wine xinput/HID hook reads via
//                          winios_pad_get_state (declared in Winios.h)
//
// Ranges on the C side are XInput-native: sticks SHORT (-32768…32767),
// triggers BYTE (0…255), buttons XINPUT_GAMEPAD_* bits. The merge below
// works in normalised Float and converts at the boundary, so a future
// DirectInput/SDL consumer gets the same values through the getter.
//
// What IS functional without any Wine hook: physical-controller detection,
// the diagnostics view (roadmap step 2), calibration persistence, and the
// touchscreen analog sticks driving this exact state (observable in the
// diagnostics + device logs). What is NOT claimed: that Uncrashed moves.
// That needs the Wine-side hook plus device validation.

/// XInput button bits (XINPUT_GAMEPAD_* from xinput.h). Kept here so the
/// Swift mapper and any future Wine-side reader agree without sharing headers.
enum XInputButtons {
    static let dpadUp:        UInt16 = 0x0001
    static let dpadDown:      UInt16 = 0x0002
    static let dpadLeft:      UInt16 = 0x0004
    static let dpadRight:     UInt16 = 0x0008
    static let start:         UInt16 = 0x0010  // Menu
    static let back:          UInt16 = 0x0020  // View
    static let leftThumb:     UInt16 = 0x0040  // L3
    static let rightThumb:    UInt16 = 0x0080  // R3
    static let leftShoulder:  UInt16 = 0x0100  // LB
    static let rightShoulder: UInt16 = 0x0200  // RB
    static let guide:         UInt16 = 0x0400
    static let buttonA:       UInt16 = 0x1000
    static let buttonB:       UInt16 = 0x2000
    static let buttonX:       UInt16 = 0x4000
    static let buttonY:       UInt16 = 0x8000

    /// Touch-mapping `.pad("…")` names from ContentView's controller catalogue.
    /// LT/RT are analog triggers, not bits — they arrive via `triggerValue`.
    static func bits(forPad name: String) -> UInt16 {
        switch name {
        case "A":     return buttonA
        case "B":     return buttonB
        case "X":     return buttonX
        case "Y":     return buttonY
        case "D↑":    return dpadUp
        case "D↓":    return dpadDown
        case "D←":    return dpadLeft
        case "D→":    return dpadRight
        case "LB":    return leftShoulder
        case "RB":    return rightShoulder
        case "LS", "L3": return leftThumb
        case "RS", "R3": return rightThumb
        case "Menu":  return start
        case "View":  return back
        case "Guide": return guide
        default:      return 0
        }
    }

    /// Full-scale trigger press for the `.pad("LT")` / `.pad("RT")` buttons.
    static func triggerValue(forPad name: String) -> Float? {
        switch name {
        case "LT": return 1.0
        case "RT": return 1.0
        default:  return nil
        }
    }
}

/// Normalised stick/trigger snapshot in game coordinates:
/// x right-positive, y UP-positive, triggers 0…1.
struct NormalisedPad {
    var lx: Float = 0, ly: Float = 0
    var rx: Float = 0, ry: Float = 0
    var lt: Float = 0, rt: Float = 0
    var buttons: UInt16 = 0

    var isActive: Bool {
        buttons != 0 || lt > 0 || rt > 0
            || abs(lx) > 0 || abs(ly) > 0 || abs(rx) > 0 || abs(ry) > 0
    }
}

/// Calibration persisted to Documents/madeira-gamepad.json.
struct GamepadCalibration: Codable, Equatable {
    var deadzone: Float = 0.12          // radial deadzone, 0…0.5
    var invertLeftY: Bool = false
    var invertRightY: Bool = false
    /// FPV throttle latch: the left virtual stick's Y persists after release
    /// (real FPV throttles are springless). Double-tap the stick to re-centre.
    var throttleLatch: Bool = false
    var rangeScale: Float = 1.0         // 0.5…1.0, scales stick thrown range

    static let `default` = GamepadCalibration()
}

/// Which touchscreen stick is being driven.
enum VirtualStickID {
    case left, right
}

final class GamepadBridge: ObservableObject {
    static let shared = GamepadBridge()

    /// Merged output for the diagnostics view (main thread).
    @Published private(set) var merged = NormalisedPad()
    @Published private(set) var controllerName: String?
    @Published private(set) var physicalConnected = false
    /// Latched once any virtual input goes active — XInput reports
    /// "connected" for the virtual pad from then on in the session.
    @Published private(set) var virtualSeen = false
    @Published var calibration = GamepadCalibration.default {
        didSet { saveCalibration() }
    }

    private var physical = NormalisedPad()
    private var virtualLeft = NormalisedPad()
    private var virtualRight = NormalisedPad()
    private var virtualButtons: UInt16 = 0
    private var virtualLT: Float = 0, virtualRT: Float = 0
    private var latchedThrottleY: Float = 0
    private var started = false
    private let lock = NSLock()

    private static var calibrationURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("madeira-gamepad.json")
    }

    private init() {
        if let d = try? Data(contentsOf: Self.calibrationURL),
           let c = try? JSONDecoder().decode(GamepadCalibration.self, from: d) {
            // Clamp in case a hand-edited file carries nonsense.
            var sane = c
            sane.deadzone = min(max(sane.deadzone, 0), 0.5)
            sane.rangeScale = min(max(sane.rangeScale, 0.5), 1.0)
            calibration = sane
        }
    }

    private func saveCalibration() {
        guard let d = try? JSONEncoder().encode(calibration) else { return }
        try? d.write(to: Self.calibrationURL, options: .atomic)
    }

    // MARK: - Lifecycle (call once from the app's root view)

    /// Roadmap §7 step 1 prep: registers connect/disconnect observation and
    /// picks up already-paired controllers. Safe to call repeatedly.
    func start() {
        guard !started else { return }
        started = true
        NotificationCenter.default.addObserver(
            forName: .GCControllerDidConnect, object: nil, queue: .main) { [weak self] _ in
            self?.rescanControllers()
        }
        NotificationCenter.default.addObserver(
            forName: .GCControllerDidDisconnect, object: nil, queue: .main) { [weak self] _ in
            self?.rescanControllers()
        }
        // Roadmap §7 step 7 / §8: interruptions cancel in-flight touches
        // without delivering gesture-end, which would leave held buttons and
        // a deflected (possibly latched-throttle) stick flying on return.
        // Release the virtual side here; the C helper releases held keys,
        // mouse buttons and the pad store on the Wine side. Physical state
        // refreshes from the next controller event.
        NotificationCenter.default.addObserver(
            forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { _ in
            GamepadBridge.shared.releaseAllVirtual()
            winios_release_all_inputs()
            LogStore.shared.log("[pad] inputs released on resign-active")
        }
        rescanControllers()
    }

    private func rescanControllers() {
        let controllers = GCController.controllers()
        guard let pad = controllers.first?.extendedGamepad else {
            lock.withPadLock { physical = NormalisedPad() }
            DispatchQueue.main.async {
                self.physicalConnected = false
                self.controllerName = nil
                self.pushMerged()
            }
            LogStore.shared.log("[pad] no extended gamepad (\(controllers.count) controller(s) seen)")
            return
        }
        let name = controllers.first?.vendorName ?? "gamepad"
        pad.valueChangedHandler = { [weak self] _, _ in self?.readPhysical(pad) }
        readPhysical(pad)
        DispatchQueue.main.async {
            self.physicalConnected = true
            self.controllerName = name
        }
        LogStore.shared.log("[pad] connected: \(name)", level: .success)
    }

    private func readPhysical(_ pad: GCExtendedGamepad) {
        var next = NormalisedPad()
        next.lx = pad.leftThumbstick.xAxis.value
        next.ly = pad.leftThumbstick.yAxis.value
        next.rx = pad.rightThumbstick.xAxis.value
        next.ry = pad.rightThumbstick.yAxis.value
        next.lt = pad.leftTrigger.value
        next.rt = pad.rightTrigger.value
        var b: UInt16 = 0
        if pad.buttonA.isPressed { b |= XInputButtons.buttonA }
        if pad.buttonB.isPressed { b |= XInputButtons.buttonB }
        if pad.buttonX.isPressed { b |= XInputButtons.buttonX }
        if pad.buttonY.isPressed { b |= XInputButtons.buttonY }
        if pad.dpad.up.isPressed { b |= XInputButtons.dpadUp }
        if pad.dpad.down.isPressed { b |= XInputButtons.dpadDown }
        if pad.dpad.left.isPressed { b |= XInputButtons.dpadLeft }
        if pad.dpad.right.isPressed { b |= XInputButtons.dpadRight }
        if pad.leftShoulder.isPressed { b |= XInputButtons.leftShoulder }
        if pad.rightShoulder.isPressed { b |= XInputButtons.rightShoulder }
        if pad.leftThumbstickButton?.isPressed == true { b |= XInputButtons.leftThumb }
        if pad.rightThumbstickButton?.isPressed == true { b |= XInputButtons.rightThumb }
        // Menu/Options/Guide buttons vary by controller/profile — deliberately
        // NOT mapped here. A mis-mapped system button that opens the iPad
        // overlay mid-flight is worse than an unmapped one; touch buttons
        // cover Menu/View/Guide through the virtual path.
        next.buttons = b
        lock.withPadLock { physical = next }
        DispatchQueue.main.async { self.pushMerged() }
    }

    // MARK: - Touchscreen writers (main thread)

    func setVirtualStick(_ id: VirtualStickID, x: Float, y: Float) {
        var slot = NormalisedPad()
        slot.lx = x; slot.ly = y
        lock.withPadLock {
            switch id {
            case .left:  virtualLeft = slot
            case .right: virtualRight = slot
            }
            if slot.isActive { virtualSeen = true }
        }
        pushMerged()
    }

    func setVirtualButton(pad name: String, down: Bool) {
        lock.withPadLock {
            if let t = XInputButtons.triggerValue(forPad: name) {
                if name == "LT" { virtualLT = down ? t : 0 }
                else { virtualRT = down ? t : 0 }
            } else {
                let bits = XInputButtons.bits(forPad: name)
                if down { virtualButtons |= bits } else { virtualButtons &= ~bits }
            }
            if down { virtualSeen = true }
        }
        pushMerged()
        // Haptic on the DOWN edge only, matching the key-button convention.
        if down { UIImpactFeedbackGenerator(style: .light).impactOccurred() }
    }

    /// Throttle latch helpers for the left virtual stick (§7: springless FPV
    /// throttle). The latch lives here — not in the view — so diagnostics and
    /// the merged output always agree on what Y is flying.
    func latchedThrottle() -> Float {
        lock.withPadLock { latchedThrottleY }
    }

    func setLatchedThrottle(_ y: Float) {
        lock.withPadLock {
            latchedThrottleY = y
            if y != 0 { virtualSeen = true }
        }
        pushMerged()
    }

    func resetLatchedThrottle() {
        setLatchedThrottle(0)
    }

    /// Release every virtual input: sticks recenter, buttons/triggers clear,
    /// latched throttle drops. Called on interruption (see start()) and safe
    /// to call any time — e.g. before a layout change mid-session.
    func releaseAllVirtual() {
        lock.withPadLock {
            virtualLeft = NormalisedPad()
            virtualRight = NormalisedPad()
            virtualButtons = 0
            virtualLT = 0
            virtualRT = 0
            latchedThrottleY = 0
        }
        pushMerged()
    }

    // MARK: - Merge + publish

    private func deadzoned(_ v: Float) -> Float {
        let dz = calibration.deadzone
        let a = abs(v)
        guard a > dz else { return 0 }
        // Rescale so the edge of the deadzone maps to 0, full throw to ±scale.
        let sign: Float = v >= 0 ? 1 : -1
        return sign * min((a - dz) / (1 - dz), 1) * calibration.rangeScale
    }

    /// Physical wins per-axis when it is outside the deadzone; otherwise the
    /// virtual (touchscreen) value flies. Buttons and triggers OR/max.
    /// Pure function of calibration + its two inputs, so device logs and the
    /// diagnostics view can attribute exactly what flew on any run.
    func merge(physical p: NormalisedPad, virtual v: NormalisedPad) -> NormalisedPad {
        var out = NormalisedPad()
        out.lx = abs(p.lx) > calibration.deadzone ? deadzoned(p.lx) : deadzoned(v.lx)
        out.ly = abs(p.ly) > calibration.deadzone
            ? deadzoned(calibration.invertLeftY ? -p.ly : p.ly)
            : deadzoned(calibration.invertLeftY ? -v.ly : v.ly)
        out.rx = abs(p.rx) > calibration.deadzone ? deadzoned(p.rx) : deadzoned(v.rx)
        out.ry = abs(p.ry) > calibration.deadzone
            ? deadzoned(calibration.invertRightY ? -p.ry : p.ry)
            : deadzoned(calibration.invertRightY ? -v.ry : v.ry)
        out.lt = max(p.lt, v.lt)
        out.rt = max(p.rt, v.rt)
        out.buttons = p.buttons | v.buttons
        return out
    }

    private static func toShort(_ v: Float) -> Int16 {
        // XInput Y is up-positive; callers pass game coordinates already.
        let clamped = min(max(v, -1), 1)
        return clamped >= 0 ? Int16(clamped * 32767) : Int16(clamped * 32768)
    }

    private func pushMerged() {
        let cal = calibration
        let (phys, vl, vr, vb, vlt, vrt, latch): (NormalisedPad, NormalisedPad, NormalisedPad, UInt16, Float, Float, Float) =
            lock.withPadLock { (physical, virtualLeft, virtualRight, virtualButtons, virtualLT, virtualRT, latchedThrottleY) }
        var virt = NormalisedPad()
        // Left touchscreen stick drives LX/LY; right drives RX/RY.
        virt.lx = vl.lx
        virt.ly = cal.throttleLatch ? latch : vl.ly
        virt.rx = vr.lx
        virt.ry = vr.ly
        virt.lt = max(vlt, vl.lt)
        virt.rt = max(vrt, vr.rt)
        virt.buttons = vb | vl.buttons | vr.buttons
        let out = merge(physical: phys, virtual: virt)
        let connected = physicalConnected || virtualSeen
        // Publish for diagnostics…
        if Thread.isMainThread {
            merged = out
        } else {
            DispatchQueue.main.async { self.merged = out }
        }
        // …and to the C store the future Wine hook will read.
        winios_pad_update(
            Int32(Self.toShort(out.lx)), Int32(Self.toShort(out.ly)),
            Int32(Self.toShort(out.rx)), Int32(Self.toShort(out.ry)),
            UInt8(min(max(out.lt, 0), 1) * 255), UInt8(min(max(out.rt, 0), 1) * 255),
            out.buttons, connected ? 1 : 0)
    }
}

// MARK: - Diagnostics (roadmap §7 step 2)

/// Raw-axes diagnostic display: connection state, physical vs merged values,
/// button bits and calibration. Read-only flight instrumentation — it proves
/// the iPad receives the controller (step 1) and that four proportional axes
/// reach the virtual pad. Calibration inside Uncrashed itself still needs the
/// device session (§7 step 5).
struct GamepadDiagnosticsView: View {
    @ObservedObject private var bridge = GamepadBridge.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle()
                    .fill(bridge.physicalConnected ? .green : .gray)
                    .frame(width: 10, height: 10)
                Text(bridge.physicalConnected
                     ? "Controller: \(bridge.controllerName ?? "gamepad")"
                     : "No physical controller — touch sticks drive the virtual pad")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.white.opacity(0.9))
            }
            axesGrid
            Text(String(format: "buttons 0x%04X  LT %.2f  RT %.2f  virtual-seen %@",
                        UInt32(bridge.merged.buttons), bridge.merged.lt, bridge.merged.rt,
                        bridge.virtualSeen ? "yes" : "no"))
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.white.opacity(0.75))
            calibrationRow
            Text("Wine XInput hook: not wired yet — this state is the source it will read (see Winios.h). Calibrate in Uncrashed once §6 launches.")
                .font(.system(size: 10))
                .foregroundStyle(.orange.opacity(0.9))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 12).fill(.white.opacity(0.08)))
    }

    private var axesGrid: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 2) {
            GridRow {
                Text("LX").mono(); Text(val(bridge.merged.lx)).mono()
                Text("LY").mono(); Text(val(bridge.merged.ly)).mono()
            }
            GridRow {
                Text("RX").mono(); Text(val(bridge.merged.rx)).mono()
                Text("RY").mono(); Text(val(bridge.merged.ry)).mono()
            }
        }
        .foregroundStyle(.white.opacity(0.85))
    }

    private func val(_ v: Float) -> String { String(format: "%+.2f", v) }

    private var calibrationRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Deadzone \(bridge.calibration.deadzone, specifier: "%.2f")")
                    .font(.system(size: 11)).foregroundStyle(.white.opacity(0.8))
                Slider(value: Binding(
                    get: { Double(bridge.calibration.deadzone) },
                    set: { bridge.calibration.deadzone = Float(min(max($0, 0), 0.5)) }),
                       in: 0...0.5, step: 0.01)
            }
            Toggle("Invert left Y", isOn: Binding(
                get: { bridge.calibration.invertLeftY },
                set: { bridge.calibration.invertLeftY = $0 }))
            Toggle("Invert right Y", isOn: Binding(
                get: { bridge.calibration.invertRightY },
                set: { bridge.calibration.invertRightY = $0 }))
            Toggle("Throttle latch (springless left-Y)", isOn: Binding(
                get: { bridge.calibration.throttleLatch },
                set: { bridge.calibration.throttleLatch = $0 }))
            HStack {
                Spacer()
                Button("Reset calibration") {
                    bridge.calibration = GamepadCalibration.default
                    bridge.resetLatchedThrottle()
                }
                .font(.system(size: 11))
            }
        }
        .font(.system(size: 11))
        .foregroundStyle(.white.opacity(0.85))
        .toggleStyle(.switch)
    }
}

private extension Text {
    func mono() -> some View {
        font(.system(size: 11, design: .monospaced)).foregroundStyle(.white.opacity(0.7))
    }
}

private extension NSLock {
    @discardableResult
    func withPadLock<T>(_ body: () -> T) -> T {
        lock(); defer { unlock() }; return body()
    }
}
