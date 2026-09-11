"""Functional tests for tools/ar-macho-symbols.py.

Builds minimal Mach-O objects and archives entirely in Python (no Apple
toolchain needed) and checks the parser the GnuTLS symtab generator depends
on: defined globals listed, everything else skipped, corrupt input rejected
fast instead of hanging.
"""
import struct
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile

spec = spec_from_file_location(
    'ar_macho_symbols', Path(__file__).with_name('ar-macho-symbols.py'))
ar = module_from_spec(spec)
spec.loader.exec_module(ar)


def nlist64(strx, n_type, sect, value):
    return struct.pack('<IBBHQ', strx, n_type, sect, 0, value)


def macho64(symbols):
    """symbols: list of (name, n_type, sect, value). Returns object bytes."""
    strings = b'\0'
    offsets = {}
    for name, _, _, _ in symbols:
        offsets[name] = len(strings)
        strings += name.encode('ascii') + b'\0'
    entries = b''.join(nlist64(offsets[n], t, s, v) for n, t, s, v in symbols)
    header = struct.pack('<IIIIIIII', 0xFEEDFACF, 0x0100000C, 0, 0x1, 1, 24, 0, 0)
    symtab = struct.pack('<IIIIII', 0x2, 24, 0, 0, 0, 0)
    symoff = len(header) + len(symtab)
    stroff = symoff + len(entries)
    symtab = struct.pack('<IIIIII', 0x2, 24, symoff, len(symbols), stroff, len(strings))
    return header + symtab + entries + strings


def ar_member(name, content):
    header = name.encode('ascii').ljust(16, b' ')[:16]
    header += b'0'.ljust(12, b' ') + b'0'.ljust(6, b' ') + b'0'.ljust(6, b' ')
    header += b'100644'.ljust(8, b' ') + str(len(content)).encode('ascii').ljust(10, b' ')
    header += b'`\n'
    return header + content + (b'\n' if len(content) & 1 else b'')


def write_archive(path, members):
    with open(path, 'wb') as stream:
        stream.write(b'!<arch>\n')
        for name, content in members:
            stream.write(ar_member(name, content))


SYMS = [
    ('_gnutls_init', 0x0F, 1, 0x1000),   # N_SECT|N_EXT -> defined
    ('_shared_count', 0x0F, 2, 0x2000),  # N_SECT|N_EXT -> defined
    ('_malloc', 0x01, 0, 0),             # N_UNDF|N_EXT, value 0 -> undefined
    ('_common_buf', 0x01, 0, 64),        # N_UNDF|N_EXT, value != 0 -> common
    ('_static_helper', 0x0E, 1, 0x3000),  # no N_EXT -> local
    ('rsc_debug', 0xE0, 0, 0),           # stab -> debug
]


class ParserTests(unittest.TestCase):
    def test_defined_globals_listed(self):
        tmp = Path(tempfile.mkdtemp()) / 'libtest.a'
        write_archive(tmp, [('short.o', macho64(SYMS))])
        self.assertEqual(ar.defined_symbols(str(tmp)),
                         ['common_buf', 'gnutls_init', 'shared_count'])

    def test_special_and_foreign_members_skipped(self):
        tmp = Path(tempfile.mkdtemp()) / 'libtest.a'
        long_name = 'very_long_member_name.o'
        table = (long_name + '/\n').encode('ascii')
        members = [
            ('__.SYMDEF', b'garbage-symdef-content'),
            ('//', table),
            ('#1/%d' % len(long_name), long_name.encode('ascii') + macho64(SYMS[:1])),
            ('/0', macho64(SYMS[1:2])),
            ('notes.txt', b'this is not an object file'),
        ]
        write_archive(tmp, members)
        self.assertEqual(ar.defined_symbols(str(tmp)), ['gnutls_init', 'shared_count'])

    def test_32bit_object(self):
        header = struct.pack('<IIIIIII', 0xFEEDFACE, 0xC, 0, 0x1, 1, 24, 0)
        strings = b'\0_fn32\0'
        entry = struct.pack('<IBBHI', 1, 0x0F, 1, 0, 0x100)
        symtab = struct.pack('<IIIIII', 0x2, 24, len(header) + 24, 1,
                             len(header) + 24 + len(entry), len(strings))
        obj = header + symtab + entry + strings
        tmp = Path(tempfile.mkdtemp()) / 'lib32.a'
        write_archive(tmp, [('x.o', obj)])
        self.assertEqual(ar.defined_symbols(str(tmp)), ['fn32'])

    def test_truncated_archive_rejected(self):
        tmp = Path(tempfile.mkdtemp()) / 'libbad.a'
        write_archive(tmp, [('x.o', macho64(SYMS))])
        with open(tmp, 'r+b') as stream:
            stream.truncate(20)
        with self.assertRaises(ValueError):
            ar.defined_symbols(str(tmp))

    def test_thin_archive_rejected(self):
        tmp = Path(tempfile.mkdtemp()) / 'libthin.a'
        with open(tmp, 'wb') as stream:
            stream.write(b'!<thin>\n')
        with self.assertRaises(ValueError):
            ar.defined_symbols(str(tmp))

    def test_invalid_bsd_name_lengths_rejected(self):
        for name in ('#1/-1', '#1/100'):
            with self.subTest(name=name):
                data = b'!<arch>\n' + ar_member(name, b'x')
                with self.assertRaisesRegex(ValueError, 'BSD long-name length'):
                    list(ar._parse_ar_members(data))

    def test_truncated_special_members_rejected(self):
        for name in ('/', '//', '/SYMDEF'):
            with self.subTest(name=name):
                data = b'!<arch>\n' + ar_member(name, b'0123456789')
                with self.assertRaisesRegex(ValueError, 'truncated archive member'):
                    list(ar._parse_ar_members(data[:-4]))

    def test_garbage_member_skipped_not_fatal(self):
        tmp = Path(tempfile.mkdtemp()) / 'libmix.a'
        write_archive(tmp, [('junk.o', b'\0' * 100), ('good.o', macho64(SYMS[:1]))])
        self.assertEqual(ar.defined_symbols(str(tmp)), ['gnutls_init'])

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            ar.defined_symbols('/nonexistent/libnope.a')


if __name__ == '__main__':
    unittest.main()
