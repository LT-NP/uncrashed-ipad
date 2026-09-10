"""Regression tests for the incomplete IPA and placeholder-input failures."""
import importlib.util
import plistlib
import struct
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'validator', Path(__file__).with_name('validate-ios-bundle.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def mach_header(kind=2, cpu=0x0100000C):
    return struct.pack('<8I', 0xFEEDFACF, cpu, 0, kind, 1, 8, 0, 0) + struct.pack('<II', 1, 8)


class ValidationTests(unittest.TestCase):
    def test_partial_app_without_executable(self):
        files = {'Info.plist': plistlib.dumps({'CFBundleExecutable': 'Madeira'})}
        with self.assertRaises(KeyError):
            validator.bundle(files.__getitem__)

    def test_wrong_architecture(self):
        with self.assertRaisesRegex(ValueError, 'ARM64'):
            validator.macho(mach_header(cpu=0x01000007), 2)

    def test_object_is_not_an_executable(self):
        with self.assertRaisesRegex(ValueError, 'file type'):
            validator.macho(mach_header(kind=1), 2)

    def test_truncated_load_commands(self):
        with self.assertRaisesRegex(ValueError, 'load commands'):
            validator.macho(mach_header()[:-1], 2)

    def test_dummy_dll(self):
        with self.assertRaises(ValueError):
            validator.pe(b'MZ\x90\x00placeholder', 0x8664)

    def test_empty_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dummy.a'
            path.write_bytes(b'!<arch>\n')
            with self.assertRaisesRegex(ValueError, 'placeholder'):
                validator.archive(path)

    def test_arm64_object_archive(self):
        body = mach_header(kind=1)
        header = (f'{"test.o/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(body):<10}`\n').encode()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'native.a'
            path.write_bytes(b'!<arch>\n' + header + body)
            validator.archive(path)

    def test_executable_header(self):
        validator.macho(mach_header(), 2)


if __name__ == '__main__':
    unittest.main()
