"""Read-only inspection of a user-owned Uncrashed installation; Python stdlib only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def inspect_pe(path):
    data = path.read_bytes()
    if data[:2] != b'MZ':
        raise ValueError(f'Not a PE: {path}')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    machine, count = struct.unpack_from('<HH', data, pe + 4)
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', data, optional)[0]
    if magic not in (0x10b, 0x20b):
        raise ValueError('Unsupported optional header')
    sections = []
    for i in range(count):
        off = optional + optional_size + i * 40
        vs, va, size, raw = struct.unpack_from('<IIII', data, off + 8)
        sections.append((va, max(vs, size), raw))

    def offset(rva):
        for va, size, raw in sections:
            if va <= rva < va + size:
                return raw + rva - va
        raise ValueError(f'Unmapped RVA {rva:x}')

    imports = []
    directory = optional + (112 if magic == 0x20b else 96)
    rva, size = struct.unpack_from('<II', data, directory + 8)
    if rva:
        off = offset(rva)
        for pos in range(off, off + size, 20):
            fields = struct.unpack_from('<IIIII', data, pos)
            if not any(fields):
                break
            name = offset(fields[3])
            imports.append(data[name:data.index(b'\0', name)].decode('ascii'))
    markers = {}
    for marker in ('D3D11RHI', 'D3D12RHI', 'VulkanRHI', '++UE4+Release-'):
        markers[marker] = any(marker.encode(enc) in data for enc in ('ascii', 'utf-16le'))
    versions = set()
    for pattern in (rb'\+\+UE4\+Release-[0-9.]+', rb'4\.(?:2[0-9])\.[0-9]+[^\x00\r\n]{0,80}'):
        versions.update(m.decode('ascii', errors='replace') for m in re.findall(pattern, data))
    return dict(machine=hex(machine), sha256=hashlib.sha256(data).hexdigest(),
                imports=sorted(imports), markers=markers, version_candidates=sorted(versions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Uncrashed FPV Drone Sim'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    exe = args.root / 'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe'
    report = inspect_pe(exe)
    files = [p for p in args.root.rglob('*') if p.is_file()]
    report['total_bytes'] = sum(p.stat().st_size for p in files)
    report['package_counts'] = {ext: sum(p.suffix.lower() == ext for p in files) for ext in ('.pak', '.ucas', '.utoc')}
    report['filename_matches_not_proof_of_anticheat'] = [str(p.relative_to(args.root)) for p in files if re.search('EasyAntiCheat|BattlEye|EOS|Denuvo|AntiCheat', p.name, re.I)]
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
