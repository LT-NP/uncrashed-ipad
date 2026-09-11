"""End-to-end test for build/crypto-unix/gen_gnutls_symtab.sh.

Runs the real generator against the real Wine sources with a crafted
libgnutls.a (minimal Mach-O members built in Python — no Apple toolchain).
Guards the wiring the parser unit tests cannot see: source scanning, table
generation, the missing-symbol (OPT) path, and a clean exit. Uses
GNUTLS_LIB_OVERRIDE/SYMTAB_OUT so the real tree is never touched.
"""
import os
import struct
import subprocess
import unittest
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build/crypto-unix/gen_gnutls_symtab.sh'
SOURCES = [
    ROOT / 'wine/dlls/bcrypt/gnutls.c',
    ROOT / 'wine/dlls/secur32/schannel_gnutls.c',
    ROOT / 'wine/dlls/crypt32/unixlib.c',
]


def macho64(symbols):
    strings, offsets = b'\0', {}
    for name in symbols:
        offsets[name] = len(strings)
        strings += name.encode('ascii') + b'\0'
    entries = b''.join(
        struct.pack('<IBBHQ', offsets[n], 0x0F, 1, 0, 0x1000 + i * 0x100)
        for i, n in enumerate(symbols))
    header = struct.pack('<IIIIIIII', 0xFEEDFACF, 0x0100000C, 0, 1, 1, 24, 0, 0)
    symoff, stroff = 32 + 24, 32 + 24 + len(entries)
    symtab = struct.pack('<IIIIII', 0x2, 24, symoff, len(symbols), stroff, len(strings))
    return header + symtab + entries + strings


def ar_member(name, content):
    header = name.encode('ascii').ljust(16, b' ')[:16]
    header += b'0'.ljust(12, b' ') + b'0'.ljust(6, b' ') + b'0'.ljust(6, b' ')
    header += b'100644'.ljust(8, b' ') + str(len(content)).encode('ascii').ljust(10, b' ')
    header += b'`\n'
    return header + content + (b'\n' if len(content) & 1 else b'')


def wanted_symbols():
    names = set()
    for source in SOURCES:
        for line in source.read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            for prefix in ('LOAD_FUNCPTR(', 'LOAD_FUNCPTR_OPT('):
                if prefix in line:
                    name = line.split(prefix, 1)[1].split(')')[0].strip()
                    if name and name != 'f':
                        names.add(name)
    return sorted(names)


class GenSymtabTests(unittest.TestCase):
    def test_generates_table_from_fake_archive(self):
        for source in SOURCES:
            self.assertTrue(source.is_file(), f'wine source missing: {source}')
        names = wanted_symbols()
        self.assertGreater(len(names), 10, 'expected many LOAD_FUNCPTR names')
        tmp = Path(tempfile.mkdtemp())
        archive = tmp / 'libgnutls.a'
        defined = names[:20]
        with open(archive, 'wb') as stream:
            stream.write(b'!<arch>\n')
            stream.write(ar_member('gnutls.o', macho64(['_' + n for n in defined])))
        out = tmp / 'symtab.c'
        env = dict(os.environ, GNUTLS_LIB_OVERRIDE=str(archive), SYMTAB_OUT=str(out))
        proc = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True, env=env,
                              timeout=120)
        self.assertEqual(proc.returncode, 0, f'stdout={proc.stdout}\nstderr={proc.stderr}')
        generated = out.read_text(encoding='utf-8')
        self.assertIn('ios_gnutls_symtab[]', generated)
        self.assertIn('ios_gnutls_dlsym', generated)
        for name in defined:
            self.assertIn(f'"{name}"', generated)
        # Undefined-but-wanted symbols are reported, not fatal (OPT path).
        self.assertIn('NOT in libgnutls.a', proc.stdout)

    def test_missing_archive_fails_fast(self):
        tmp = Path(tempfile.mkdtemp())
        env = dict(os.environ,
                   GNUTLS_LIB_OVERRIDE=str(tmp / 'absent.a'),
                   SYMTAB_OUT=str(tmp / 'symtab.c'))
        proc = subprocess.run(['bash', str(SCRIPT)], capture_output=True, text=True, env=env,
                              timeout=120)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('ERROR', proc.stderr)


if __name__ == '__main__':
    unittest.main()
