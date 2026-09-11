"""Regression coverage for Burn CAB selection and incomplete runtime failures."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'extract_vcruntime', Path(__file__).with_name('extract-vcruntime.py'))
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


def structural_dll(machine=0x8664):
    # Deliberately synthetic, for structural validation tests only. Never bundled.
    data = bytearray(536)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 64)
    data[64:68] = b'PE\0\0'
    struct.pack_into('<HH', data, 68, machine, 1)
    struct.pack_into('<HH', data, 84, 240, 0x2002)
    struct.pack_into('<H', data, 88, 0x20B)
    struct.pack_into('<I', data, 88 + 108, 16)
    struct.pack_into('<II', data, 88 + 144, 520, 16)
    struct.pack_into('<II', data, 328 + 16, 8, 512)
    struct.pack_into('<IHH', data, 520, 16, 0x200, 2)
    data[528] = 0x30
    return data


def cabinet():
    data = bytearray(64)
    data[:4] = b'MSCF'
    struct.pack_into('<I', data, 8, len(data))
    struct.pack_into('<I', data, 16, 44)
    data[24:26] = b'\x03\x01'
    struct.pack_into('<HH', data, 26, 1, 1)
    return bytes(data)


class RuntimeTests(unittest.TestCase):
    def test_both_burn_containers_are_found(self):
        blob = b'MZ' + cabinet() + b'installer certificate' + cabinet()
        self.assertEqual(list(extractor.cabinet_ranges(blob)), [(2, 64), (87, 64)])

    def test_truncated_cab_is_not_extracted(self):
        self.assertEqual(list(extractor.cabinet_ranges(b'MZ' + cabinet()[:-1])), [])

    def test_architecture_suffixes(self):
        self.assertEqual(extractor.runtime_name('MSVCP140.dll_amd64'), 'msvcp140.dll')
        self.assertEqual(extractor.runtime_name('vcruntime140.dll_x64'), 'vcruntime140.dll')
        self.assertIsNone(extractor.runtime_name('vcruntime140.dll_arm64'))

    def test_placeholder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DOS header'):
            extractor.validate_dll(b'MZ\x90\x00placeholder')

    def test_wrong_architecture_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AMD64'):
            extractor.validate_dll(structural_dll(0xAA64))

    def test_stripped_signature_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'certificate table'):
            extractor.validate_dll(structural_dll()[:520])

    def test_truncated_section_is_rejected(self):
        data = structural_dll()
        struct.pack_into('<I', data, 328 + 16, 128)
        with self.assertRaisesRegex(ValueError, 'PE section'):
            extractor.validate_dll(data)

    def test_corrupt_certificate_length_is_rejected(self):
        data = structural_dll()
        struct.pack_into('<I', data, 520, 24)
        with self.assertRaisesRegex(ValueError, 'WIN_CERTIFICATE'):
            extractor.validate_dll(data)

    def test_complete_structure_is_accepted_without_claiming_trust(self):
        extractor.validate_dll(structural_dll())

    def test_nested_cab_after_ui_and_suffixed_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer = root / 'redist.exe'
            installer.write_bytes(b'MZ' + cabinet() + cabinet())
            work = root / 'work'
            work.mkdir()

            def unpack(_sevenzip, archive, destination):
                destination.mkdir()
                if archive.name == 'embedded-1.cab':
                    (destination / 'a12').write_bytes(cabinet())
                elif archive.name == 'a12':
                    for name in extractor.EXPECTED:
                        (destination / (name + '_amd64')).write_bytes(structural_dll())
                    (destination / 'msvcp140.dll_arm64').write_bytes(structural_dll(0xAA64))

            with patch.object(extractor, 'run_extract', side_effect=unpack):
                found = extractor.collect_runtime(installer, work, '7z')
            self.assertEqual(set(found), set(extractor.EXPECTED))

    def test_missing_payload_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installer = root / 'redist.exe'
            installer.write_bytes(b'MZ' + cabinet())
            work = root / 'work'
            work.mkdir()

            def unpack(_sevenzip, _archive, destination):
                destination.mkdir()
                (destination / 'msvcp140.dll_amd64').write_bytes(structural_dll())

            with patch.object(extractor, 'run_extract', side_effect=unpack):
                with self.assertRaisesRegex(ValueError, 'missing required x64 DLLs'):
                    extractor.collect_runtime(installer, work, '7z')

    def test_failed_validation_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'out'
            output.mkdir()
            old = output / 'msvcp140.dll'
            old.write_bytes(b'existing runtime')
            valid, invalid = root / 'valid.dll', root / 'invalid.dll'
            valid.write_bytes(structural_dll())
            invalid.write_bytes(b'placeholder')
            found = {name: valid for name in extractor.EXPECTED}
            found[extractor.EXPECTED[-1]] = invalid
            with self.assertRaises(ValueError):
                extractor.install_runtime(found, output)
            self.assertEqual(old.read_bytes(), b'existing runtime')
            self.assertEqual(list(output.iterdir()), [old])


if __name__ == '__main__':
    unittest.main()
