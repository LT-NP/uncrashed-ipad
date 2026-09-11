"""Functional tests for tools/audit-uncrashed.py.

Covers what the deploy flow depends on: PE parsing (valid/truncated/
non-PE), Steam/input markers, pak-count and size warnings, and report
output handling. Uses synthetic trees, never the real 19 GiB install.
"""
import importlib.util
import json
import struct
import unittest
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location(
    'audit_uncrashed', Path(__file__).with_name('audit-uncrashed.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def minimal_pe(machine=0x8664, marker=b'D3D11RHI'):
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<HH', data, 68, machine, 0)  # no sections
    struct.pack_into('<H', data, 84, 240)  # optional_size
    struct.pack_into('<H', data, 88, 0x20B)  # PE32+
    return bytes(data) + bytes(marker)


def make_tree(files):
    tmp = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return tmp


class InspectPeTests(unittest.TestCase):
    def test_valid_amd64(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'game.exe'
            exe.write_bytes(minimal_pe())
            report = audit.inspect_pe(exe)
        self.assertEqual(report['machine'], hex(0x8664))
        self.assertTrue(report['markers']['D3D11RHI'])
        self.assertEqual(report['imports'], [])

    def test_non_pe_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'game.exe'
            exe.write_bytes(b'not a binary')
            with self.assertRaises(ValueError):
                audit.inspect_pe(exe)

    def test_truncated_header_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'game.exe'
            exe.write_bytes(b'MZ' + b'\0' * 10)
            with self.assertRaises(ValueError):
                audit.inspect_pe(exe)

    def test_absurd_section_count_rejected(self):
        data = bytearray(minimal_pe())
        struct.pack_into('<HH', data, 68, 0x8664, 500)
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'game.exe'
            exe.write_bytes(bytes(data))
            with self.assertRaises(ValueError):
                audit.inspect_pe(exe)


class SummarizeTests(unittest.TestCase):
    def _report(self, extra_files):
        files = {'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe':
                 minimal_pe()}
        files.update(extra_files)
        root = make_tree(files)
        report = audit.inspect_pe(
            root / 'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe')
        return audit.summarize_game(root, report, audit.collect_game_files(root))

    def test_steam_dll_predicts_steam_blocker(self):
        report = self._report({'Uncrashed/Binaries/Win64/steam_api64.dll': b'x'})
        self.assertTrue(report['has_steam_api64'])
        self.assertEqual(report['likely_first_blocker'], 'steam')

    def test_no_steam_with_d3d11_predicts_renderer(self):
        report = self._report({})
        self.assertFalse(report['has_steam_api64'])
        self.assertEqual(report['likely_first_blocker'], 'renderer-or-input')

    def test_few_paks_warn(self):
        report = self._report({'Uncrashed/Content/Paks/a.pak': b'x'})
        self.assertIn('warning', report)
        self.assertEqual(report['package_counts']['.pak'], 1)

    def test_small_tree_warns_about_size(self):
        report = self._report({})
        self.assertIn('expected ~19 GiB', report.get('warning', ''))

    def test_anticheat_name_listed_but_not_verdict(self):
        report = self._report({'EasyAntiCheat/eac.exe': b'x'})
        self.assertTrue(any('EasyAntiCheat' in m for m in
                            report['filename_matches_not_proof_of_anticheat']))


class MainTests(unittest.TestCase):
    def test_missing_exe_writes_error_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'sub' / 'audit.json'
            root = Path(tmp) / 'empty'
            root.mkdir()
            import io
            import sys
            from contextlib import redirect_stdout
            argv = sys.argv
            sys.argv = ['audit-uncrashed.py', '--root', str(root),
                        '--output', str(out)]
            try:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(audit.main(), 0)
            finally:
                sys.argv = argv
            report = json.loads(out.read_text())
            self.assertIn('error', report)


if __name__ == '__main__':
    unittest.main()
