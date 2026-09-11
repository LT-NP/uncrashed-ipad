"""Functional tests for tools/check-build-inputs.py.

Covers what CI depends on: PBX group resolution, present/missing/empty/
invalid-archive/outside-repository statuses, the extra runtime-DLL checks,
and the ready_for_compile_attempt gate. Uses synthetic projects, never the
real 3000-line pbxproj.
"""
import importlib.util
import json
import unittest
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location(
    'check_inputs', Path(__file__).with_name('check-build-inputs.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

GROOT = 'AAAAAAAA00000001'


def write_project(root, refs, extra_files=()):
    """Write a minimal pbxproj with one root group containing refs.

    refs: list of (hexid, isa, sourceTree, path-or-None).
    """
    children = ' '.join(r[0] for r in refs if r[1] == 'PBXFileReference')
    lines = [f'{GROOT} = {{isa = PBXGroup; children = ({children}); sourceTree = "<group>";}};']
    for hexid, isa, tree, path in refs:
        entry = f'{hexid} = {{isa = {isa}; sourceTree = {tree};'
        if path is not None:
            entry += f' path = {path};'
        entry += '};'
        lines.append(entry)
    projdir = root / 'app/Madeira.xcodeproj'
    projdir.mkdir(parents=True, exist_ok=True)
    (projdir / 'project.pbxproj').write_text('\n'.join(lines) + '\n')
    for rel, content in extra_files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    return root


def by_path(report, path):
    return next(c for c in report['checks'] if c['path'] == path)


class StatusTests(unittest.TestCase):
    def test_present_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<group>', 'Foo.swift'),
                ('BBBBBBBB00000002', 'PBXFileReference', '<group>', 'Gone.swift'),
            ], [('app/Foo.swift', b'x')])
            report = check.inspect(root)
        self.assertEqual(by_path(report, 'app/Foo.swift')['status'], 'present')
        self.assertEqual(by_path(report, 'app/Gone.swift')['status'], 'missing')
        self.assertFalse(report['ready_for_compile_attempt'])

    def test_sdkroot_skipped_and_empty_and_bad_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', 'SDKROOT', 'UIKit.framework'),
                ('BBBBBBBB00000002', 'PBXFileReference', '<group>', 'Empty.swift'),
                ('BBBBBBBB00000003', 'PBXFileReference', '<group>', 'libx.a'),
            ], [('app/Empty.swift', b''),
                ('app/libx.a', b'not an archive at all............')])
            report = check.inspect(root)
        paths = [c['path'] for c in report['checks']]
        self.assertNotIn('UIKit.framework', paths)
        self.assertEqual(by_path(report, 'app/Empty.swift')['status'], 'empty')
        self.assertEqual(by_path(report, 'app/libx.a')['status'], 'invalid_archive')

    def test_valid_archive_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<group>', 'libv.a'),
            ], [('app/libv.a', b'!<arch>\n')])
            report = check.inspect(root)
        # 8-byte magic passes the presence check here; the stricter
        # validate-ios-bundle.py rejects it as placeholder (by design).
        self.assertEqual(by_path(report, 'app/libv.a')['status'], 'present')

    def test_outside_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<group>', '../../evil'),
            ])
            report = check.inspect(root)
        self.assertEqual(report['checks'][0]['status'], 'outside_repository')

    def test_unsupported_reference_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<absolute>', '/etc/passwd'),
            ])
            with self.assertRaises(ValueError):
                check.inspect(root)

    def test_missing_project_raises_oserror(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                check.inspect(Path(tmp))


class GateTests(unittest.TestCase):
    EXTRA = (
        'app/Madeira/arm64ec-windows/ntdll.dll',
        'app/Madeira/arm64ec-windows/xtajit64.dll',
        'app/Madeira/aarch64-windows/ntdll.dll',
        'app/Madeira/aarch64-windows/d3d11.dll',
        'app/Madeira/aarch64-windows/dxgi.dll',
        'app/Madeira/x86_64-vcruntime/msvcp140.dll',
        'app/Madeira/x86_64-vcruntime/vcruntime140.dll',
        'app/Madeira/x86_64-vcruntime/vcruntime140_1.dll',
    )

    def test_ready_only_when_everything_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<group>', 'Foo.swift'),
            ], [('app/Foo.swift', b'x')] +
                [(rel, b'MZ' + b'\0' * 62) for rel in self.EXTRA])
            report = check.inspect(root)
        self.assertTrue(report['ready_for_compile_attempt'])

    def test_main_exit_codes(self):
        import io
        import sys
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = Path(tmp) / 'audit.json'
            write_project(root, [
                ('BBBBBBBB00000001', 'PBXFileReference', '<group>', 'Gone.swift'),
            ])
            argv = sys.argv
            sys.argv = ['check-build-inputs.py', '--root', str(root),
                        '--output', str(out)]
            try:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(check.main(), 1)
            finally:
                sys.argv = argv
            saved = json.loads(out.read_text())
            self.assertFalse(saved['ready_for_compile_attempt'])


if __name__ == '__main__':
    unittest.main()
