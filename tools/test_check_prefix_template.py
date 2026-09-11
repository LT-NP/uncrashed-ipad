"""Functional tests for tools/check-prefix-template.sh.

Covers what the IPA job depends on: a clean prefix passes, an archive
with an absolute host symlink fails, and a missing archive fails. Builds
tiny tarballs on the fly; no device or Wine needed.
"""
import subprocess
import tarfile
import unittest
from pathlib import Path
import tempfile

SCRIPT = Path(__file__).with_name('check-prefix-template.sh')


def make_archive(path, symlink_to=None):
    with tarfile.open(path, 'w:gz') as tar:
        reg = tarfile.TarInfo('prefix/system.reg')
        data = b'WINE REGISTRY Version 2\n'
        reg.size = len(data)
        import io
        tar.addfile(reg, io.BytesIO(data))
        if symlink_to is not None:
            link = tarfile.TarInfo('prefix/drive_c/users/madeira/Documents')
            link.type = tarfile.SYMTYPE
            link.linkname = symlink_to
            tar.addfile(link)


class PrefixTemplateTests(unittest.TestCase):
    def run_check(self, archive):
        return subprocess.run(['sh', str(SCRIPT), str(archive)],
                              capture_output=True, text=True)

    def test_clean_archive_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'prefix-template.tar.gz'
            make_archive(archive)
            result = self.run_check(archive)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK', result.stdout)

    def test_absolute_host_symlink_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'prefix-template.tar.gz'
            make_archive(archive, symlink_to='/Users/someone/Documents')
            result = self.run_check(archive)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL', result.stderr)

    def test_tmp_symlink_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'prefix-template.tar.gz'
            make_archive(archive, symlink_to='/tmp/foo')
            result = self.run_check(archive)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_archive_fails(self):
        result = self.run_check(Path('/nonexistent/prefix-template.tar.gz'))
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
