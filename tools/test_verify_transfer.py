"""Functional tests for the §5 transfer verification flow.

Covers manifest building (tools/audit-uncrashed.py --manifest) and
comparison (tools/verify-uncrashed-transfer.py): clean copies pass,
missing/truncated/corrupt files fail, extras only inform, a nested
duplicate game directory fails, and the shipping-exe gate works. Uses
synthetic trees, never the real 19 GiB install.
"""
import importlib.util
import shutil
import unittest
from pathlib import Path
import tempfile

HERE = Path(__file__).parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load('audit-uncrashed')
verify_mod = load('verify-uncrashed-transfer')

EXE = 'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe'


def make_source():
    tmp = Path(tempfile.mkdtemp())
    files = {
        EXE: b'MZ-fake-exe' * 100,
        'Uncrashed/Binaries/Win64/steam_api64.dll': b'steam' * 50,
        'Uncrashed/Content/Paks/pakchunk0-WindowsNoEditor.pak': bytes(1000),
        'Uncrashed/Content/Paks/pakchunk1-WindowsNoEditor.pak': bytes(2000),
        'Engine/Config/Base.ini': b'[core]\n',
    }
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return tmp


def manifest_for(source, **kwargs):
    files = audit.collect_game_files(source)
    return audit.build_manifest(source, files, **kwargs)


class ManifestTests(unittest.TestCase):
    def test_manifest_lists_everything_sorted(self):
        source = make_source()
        manifest = manifest_for(source)
        self.assertEqual(manifest['version'], 1)
        self.assertEqual(manifest['total_files'], 5)
        paths = [e['path'] for e in manifest['files']]
        self.assertEqual(paths, sorted(paths))
        self.assertIn(EXE, paths)

    def test_manifest_hashes_small_files_by_default(self):
        source = make_source()
        manifest = manifest_for(source)
        by_path = {e['path']: e for e in manifest['files']}
        self.assertIsNotNone(by_path[EXE]['sha256'])
        self.assertEqual(manifest['total_bytes'],
                         sum(e['size'] for e in manifest['files']))

    def test_manifest_skips_hash_above_limit_unless_forced(self):
        source = make_source()
        small = manifest_for(source, hash_limit_mb=0)
        self.assertTrue(all(e['sha256'] is None for e in small['files']))
        forced = manifest_for(source, hash_limit_mb=0, hash_all=True)
        self.assertTrue(all(e['sha256'] for e in forced['files']))


class VerifyTests(unittest.TestCase):
    def test_clean_copy_passes(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertTrue(ok, result)
        self.assertTrue(result['exe_present'])
        self.assertEqual(result['extra_files'], 0)

    def test_missing_file_fails(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        (dest / 'Uncrashed/Content/Paks/pakchunk1-WindowsNoEditor.pak').unlink()
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertFalse(ok)
        self.assertEqual(len(result['missing']), 1)

    def test_truncated_file_fails_by_size(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        p = dest / 'Uncrashed/Content/Paks/pakchunk0-WindowsNoEditor.pak'
        p.write_bytes(bytes(500))
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertFalse(ok)
        self.assertEqual(len(result['size_mismatched']), 1)

    def test_corrupt_small_file_fails_by_hash(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        p = dest / EXE
        data = bytearray(p.read_bytes())
        data[10] ^= 0xFF
        p.write_bytes(bytes(data))
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertFalse(ok)
        self.assertIn(EXE, result['hash_mismatched'])

    def test_extra_files_do_not_fail(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        (dest / 'SaveGames').mkdir()
        (dest / 'SaveGames/save.sav').write_bytes(b'data')
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertTrue(ok, result)
        self.assertEqual(result['extra_files'], 1)

    def test_nested_duplicate_dir_fails(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'Uncrashed FPV Drone Sim'
        dest.mkdir()
        shutil.copytree(source, dest / 'Uncrashed FPV Drone Sim')
        ok, result = verify_mod.verify(manifest_for(source), dest / 'Uncrashed FPV Drone Sim')
        # Sanity: manifest rooted at source still verifies against the copy…
        self.assertTrue(ok, result)
        # …but pointing the verifier at the outer dir flags the nesting.
        outer_manifest = manifest_for(source)
        ok2, result2 = verify_mod.verify(outer_manifest, dest)
        self.assertFalse(ok2)
        self.assertTrue(result2['nested_duplicate_dirs'])

    def test_missing_exe_fails(self):
        source = make_source()
        dest = Path(tempfile.mkdtemp()) / 'copy'
        shutil.copytree(source, dest)
        (dest / EXE).unlink()
        ok, result = verify_mod.verify(manifest_for(source), dest)
        self.assertFalse(ok)
        self.assertFalse(result['exe_present'])


if __name__ == '__main__':
    unittest.main()
