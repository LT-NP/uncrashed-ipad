"""Regression tests for the incomplete IPA and placeholder-input failures."""
import importlib.util
import io
import plistlib
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'validator', Path(__file__).with_name('validate-ios-bundle.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def mach_header(kind=2, cpu=0x0100000C):
    return struct.pack('<8I', 0xFEEDFACF, cpu, 0, kind, 1, 8, 0, 0) + struct.pack('<II', 1, 8)


def pe_image(cpu):
    data = bytearray(240)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<HH', data, 68, cpu, 1)
    struct.pack_into('<H', data, 84, 112)
    struct.pack_into('<H', data, 88, 0x20B)
    return bytes(data)


def prefix_image():
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as prefix:
        for name in ('system.reg', 'user.reg', 'userdef.reg'):
            member = tarfile.TarInfo(f'prefix/{name}')
            data = b'WINE REGISTRY Version 2\n'
            member.size = len(data)
            prefix.addfile(member, io.BytesIO(data))
        member = tarfile.TarInfo('prefix/drive_c/windows/system32')
        member.type = tarfile.DIRTYPE
        prefix.addfile(member)
    return stream.getvalue()


def resource_reader(overrides=None):
    overrides = overrides or {}

    def read(name):
        if name in overrides:
            if overrides[name] is None:
                raise FileNotFoundError(name)
            return overrides[name]
        if name == 'prefix-template.tar.gz':
            return prefix_image()
        return pe_image(0xAA64 if name.startswith('aarch64-windows/') else 0x8664)
    return read


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

    def test_runtime_resources(self):
        validator.runtime_resources(resource_reader())

    def test_missing_translation_dll(self):
        with self.assertRaisesRegex(FileNotFoundError, 'xtajit64'):
            validator.runtime_resources(resource_reader({'arm64ec-windows/xtajit64.dll': None}))

    def test_wrong_graphics_architecture(self):
        with self.assertRaisesRegex(ValueError, 'architecture'):
            validator.runtime_resources(resource_reader({'aarch64-windows/d3d11.dll': pe_image(0x8664)}))

    def test_dummy_prefix(self):
        with self.assertRaises((tarfile.TarError, EOFError)):
            validator.runtime_resources(resource_reader({'prefix-template.tar.gz': b'\x1f\x8bplaceholder'}))

    def test_prefix_missing_registry(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz'):
            pass
        with self.assertRaisesRegex(KeyError, 'system.reg'):
            validator.runtime_resources(resource_reader({'prefix-template.tar.gz': stream.getvalue()}))

    def test_plist_root_not_dict(self):
        files = {'Info.plist': plistlib.dumps([1, 2, 3])}
        with self.assertRaisesRegex(ValueError, 'dictionary'):
            validator.bundle(files.__getitem__)

    def test_main_reports_invalid_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            plist = Path(tmp) / 'Info.plist'
            plist.write_bytes(plistlib.dumps([1, 2, 3]))
            # bundle() raises ValueError which main() must convert to returncode 1
            with self.assertRaises(ValueError):
                validator.bundle(lambda name: plist.read_bytes())


if __name__ == '__main__':
    unittest.main()
