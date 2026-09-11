"""Structural tests for the POST_BUILD_ROADMAP §7 gamepad bridge.

The controller work is app-side state (Swift GamepadBridge + winios pad
store) pending §6 runtime evidence for the Wine-side hook, so there is no
device behavior to assert here. These tests pin the wiring instead: the
Xcode project includes the new source, the C bridge is declared AND
defined, the Swift UI routes pad/analog input into the bridge (never the
old inert stub), and the StikDebug scheme probe covers both URL schemes.

Uses the real repo files, never a device or compiler.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / 'app/Madeira/GamepadBridge.swift'
CONTENT = ROOT / 'app/Madeira/ContentView.swift'
WINIOS_H = ROOT / 'app/Madeira/Winios/Winios.h'
WINIOS_M = ROOT / 'app/Madeira/Winios/Winios.m'
PBXPROJ = ROOT / 'app/Madeira.xcodeproj/project.pbxproj'
PLIST = ROOT / 'app/Madeira/Info.plist'
JIT_HELPER = ROOT / 'app/Madeira/StikJITHelper.swift'

EXPECTED_BUTTONS = {
    'dpadUp': 0x0001, 'dpadDown': 0x0002, 'dpadLeft': 0x0004,
    'dpadRight': 0x0008, 'start': 0x0010, 'back': 0x0020,
    'leftThumb': 0x0040, 'rightThumb': 0x0080,
    'leftShoulder': 0x0100, 'rightShoulder': 0x0200, 'guide': 0x0400,
    'buttonA': 0x1000, 'buttonB': 0x2000, 'buttonX': 0x4000,
    'buttonY': 0x8000,
}


class GamepadBridgeTests(unittest.TestCase):
    def test_bridge_file_exists(self):
        self.assertTrue(BRIDGE.is_file(), 'GamepadBridge.swift missing')

    def test_xinput_button_bits(self):
        text = BRIDGE.read_text(encoding='utf-8')
        for name, value in EXPECTED_BUTTONS.items():
            match = re.search(
                r'static let %s:\s*UInt16\s*=\s*(0x[0-9a-fA-F]+)' % name, text)
            self.assertIsNotNone(match, f'XInput bit missing: {name}')
            self.assertEqual(int(match.group(1), 16), value,
                             f'Wrong XInput bit for {name}')

    def test_bridge_publishes_to_c_store(self):
        text = BRIDGE.read_text(encoding='utf-8')
        self.assertIn('winios_pad_update', text)
        self.assertIn('func merge(physical', text)
        self.assertIn('GamepadDiagnosticsView', text)
        self.assertIn('GCController', text)

    def test_pad_names_cover_catalogue(self):
        text = BRIDGE.read_text(encoding='utf-8')
        for name in ['"A"', '"B"', '"X"', '"Y"', '"D↑"', '"LB"', '"LT"',
                     '"LS"', '"Menu"', '"Guide"']:
            self.assertIn(name, text, f'pad name unmapped: {name}')

    def test_c_bridge_declared_and_defined(self):
        header = WINIOS_H.read_text(encoding='utf-8')
        impl = WINIOS_M.read_text(encoding='utf-8')
        for symbol in ('winios_pad_update', 'winios_pad_get_state'):
            self.assertIn(symbol, header, f'{symbol} not declared in Winios.h')
            self.assertRegex(impl, r'\b%s\s*\(' % symbol,
                             f'{symbol} not defined in Winios.m')

    def test_pad_actions_drive_bridge(self):
        text = CONTENT.read_text(encoding='utf-8')
        self.assertIn('case .analogLeft', text)
        self.assertIn('case .analogRight', text)
        self.assertIn('GamepadBridge.shared.setVirtualButton(pad:', text)
        self.assertIn('AnalogStickControlView', text)
        self.assertIn('GamepadBridge.shared.start()', text)
        self.assertNotIn('deliberately inert', text)

    def test_controller_tab_lists_analog(self):
        text = CONTENT.read_text(encoding='utf-8')
        self.assertIn('.analogLeft', text)
        self.assertIn('.analogRight', text)

    def test_pbxproj_includes_bridge(self):
        text = PBXPROJ.read_text(encoding='utf-8')
        self.assertIn('GamepadBridge.swift in Sources', text)
        self.assertIn('GamepadBridge.swift', text)
        # Referenced file must exist or check-build-inputs.py reports missing.
        self.assertTrue(BRIDGE.is_file())

    def test_stikdebug_scheme_probe(self):
        plist = PLIST.read_text(encoding='utf-8')
        self.assertIn('stikdebug', plist)
        helper = JIT_HELPER.read_text(encoding='utf-8')
        self.assertIn('stikdebugAvailable', helper)
        self.assertIn('stikjitAvailable', helper)
        # Legacy path is kept as fallback, not replaced.
        self.assertIn('stikjit://enable-jit', helper)

    def test_default_flight_layout(self):
        # First launch must offer sticks + minimal buttons (§7 step 6),
        # without ever overwriting a saved layout.
        text = CONTENT.read_text(encoding='utf-8')
        self.assertIn('static var defaultControls', text)
        body = text.split('static var defaultControls', 1)[1].split('private init()', 1)[0]
        for action in ('.analogLeft', '.analogRight', '.pad("A")',
                       '.pad("B")', '.pad("Menu")'):
            self.assertIn(action, body, f'default layout missing {action}')

    def test_interruption_releases_inputs(self):
        bridge = BRIDGE.read_text(encoding='utf-8')
        self.assertIn('willResignActiveNotification', bridge)
        self.assertIn('func releaseAllVirtual', bridge)
        self.assertIn('winios_release_all_inputs', bridge)
        header = WINIOS_H.read_text(encoding='utf-8')
        impl = WINIOS_M.read_text(encoding='utf-8')
        self.assertIn('winios_release_all_inputs', header)
        self.assertRegex(impl, r'\bwinios_release_all_inputs\s*\(')
        # Held-key tracking must exist or release-all is a no-op.
        self.assertIn('g_held_vk', impl)

    def test_stikdebug_url_carries_pid(self):
        # INTEGRATION.md Part 2: the URL always includes bundle ID and PID;
        # custom-script apps send base64 script-data.
        helper = JIT_HELPER.read_text(encoding='utf-8')
        self.assertIn('"stikdebug"', helper)
        self.assertIn('"enable-jit"', helper)
        self.assertIn('"bundle-id"', helper)
        self.assertIn('"pid"', helper)
        self.assertIn('"script-data"', helper)
        self.assertIn('getpid()', helper)


if __name__ == '__main__':
    unittest.main()
