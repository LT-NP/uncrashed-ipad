"""Read-only inspection of a user-owned Uncrashed installation; Python stdlib only."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import re
import struct


def inspect_pe(path):
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError(f'Not a PE: {path}')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if pe < 0 or pe + 24 > len(data) or data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    machine, count = struct.unpack_from('<HH', data, pe + 4)
    if count > 96:
        raise ValueError(f'Invalid PE section count: {count}')
    optional_size = struct.unpack_from('<H', data, pe + 20)[0]
    optional = pe + 24
    if optional + 2 > len(data):
        raise ValueError('Truncated PE optional header')
    magic = struct.unpack_from('<H', data, optional)[0]
    if magic not in (0x10b, 0x20b):
        raise ValueError('Unsupported optional header')
    if optional + optional_size + count * 40 > len(data):
        raise ValueError('Truncated PE section table')
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
    if directory + 16 > len(data):
        raise ValueError('Truncated PE data directory')
    rva, size = struct.unpack_from('<II', data, directory + 8)
    if size > 16 * 1024 * 1024:
        raise ValueError(f'Invalid PE import directory size: {size}')
    if rva:
        off = offset(rva)
        if off + size > len(data):
            raise ValueError('Truncated PE import directory')
        for pos in range(off, off + size, 20):
            if pos + 20 > len(data):
                break
            fields = struct.unpack_from('<IIIII', data, pos)
            if not any(fields):
                break
            name = offset(fields[3])
            end = data.find(b'\0', name)
            if end < 0:
                raise ValueError('Unterminated PE import name')
            try:
                imports.append(data[name:end].decode('ascii'))
            except UnicodeDecodeError as e:
                raise ValueError(f'Invalid PE import name encoding: {e}')
    markers = {}
    for marker in ('D3D11RHI', 'D3D12RHI', 'VulkanRHI', '++UE4+Release-'):
        markers[marker] = any(marker.encode(enc) in data for enc in ('ascii', 'utf-16le'))
    versions = set()
    for pattern in (rb'\+\+UE4\+Release-[0-9.]+', rb'4\.(?:2[0-9])\.[0-9]+[^\x00\r\n]{0,80}'):
        versions.update(m.decode('ascii', errors='replace') for m in re.findall(pattern, data))
    return dict(machine=hex(machine), sha256=hashlib.sha256(data).hexdigest(),
                imports=sorted(imports), markers=markers, version_candidates=sorted(versions))


def collect_game_files(root):
    """List files under root, skipping entries that vanish mid-walk."""
    files = []
    for p in root.rglob('*'):
        try:
            if p.is_file():
                files.append(p)
        except OSError:
            continue
    return files


def total_bytes(files):
    total = 0
    for p in files:
        try:
            total += p.stat().st_size
        except OSError:
            continue
    return total


def summarize_game(root, report, files):
    """Add packaging/input/Steam markers to a successful PE report.

    File presence is not proof of a runtime requirement; it tells the
    device tester what to watch for in the first launch log (Steam init
    hang vs d3d11 vs input mapping).
    """
    report['total_bytes'] = total_bytes(files)
    report['package_counts'] = {ext: sum(p.suffix.lower() == ext for p in files)
                                for ext in ('.pak', '.ucas', '.utoc')}
    matches = []
    for p in files:
        try:
            rel = str(p.relative_to(root))
        except (ValueError, OSError):
            continue
        if re.search('EasyAntiCheat|BattlEye|EOS|Denuvo|AntiCheat', rel, re.I):
            matches.append(rel)
    report['filename_matches_not_proof_of_anticheat'] = matches
    # Check expected VCRuntime files alongside the exe (game ships them, but we also bundle them in app/Madeira)
    for dll in ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'):
        report[f'has_{dll}'] = (root / f'Uncrashed/Binaries/Win64/{dll}').is_file()
    # Warn if pak count is unexpected (Uncrashed has ~33 paks, not utoc/ucas)
    if report['package_counts'].get('.pak', 0) < 5:
        report['warning'] = "Unusually few .pak files — copy may be incomplete"
    win64 = root / 'Uncrashed/Binaries/Win64'
    report['has_steam_api64'] = (win64 / 'steam_api64.dll').is_file()
    report['has_steam_api'] = (win64 / 'steam_api.dll').is_file()
    report['has_sdl2'] = any((win64 / n).is_file() for n in ('SDL2.dll', 'SDL2-2.0.dll'))
    report['has_xinput'] = any((win64 / n).is_file()
                               for n in ('xinput1_3.dll', 'xinput1_4.dll', 'xinput9_1_0.dll'))
    imports_lower = [i.lower() for i in report.get('imports', [])]
    report['imports_xinput'] = any('xinput' in i for i in imports_lower)
    report['imports_steam'] = any('steam' in i for i in imports_lower)
    report['imports_sdl2'] = any('sdl2' in i for i in imports_lower)
    # First-failure hint for the iPad run: Steam init is the most common
    # UE4 shipping-build blocker under Wine, before d3d11/renderer.
    if report.get('has_steam_api64') or report.get('imports_steam'):
        report['likely_first_blocker'] = "steam"
    elif not report.get('markers', {}).get('D3D11RHI'):
        report['likely_first_blocker'] = "rhi"
    else:
        report['likely_first_blocker'] = "renderer-or-input"
    # Storage sanity for the 19 GiB transfer (see scripts/deploy-uncrashed.sh).
    gib = report['total_bytes'] / (1024 ** 3)
    if gib and gib < 5:
        report['warning'] = (report.get('warning', '') + " | total <5 GiB, expected ~19 GiB").strip(' |')
    return report


def write_report(output, report):
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    except OSError as e:
        print(f"Failed to write output {output}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Uncrashed FPV Drone Sim'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    exe = args.root / 'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe'
    try:
        report = inspect_pe(exe)
    except Exception as e:
        print(f"Failed to inspect PE: {e}", file=sys.stderr)
        report = dict(error=str(e), exe=str(exe))
        files = []
        report['total_bytes'] = 0
        report['package_counts'] = {}
    else:
        files = collect_game_files(args.root)
        summarize_game(args.root, report, files)
    return write_report(args.output, report)


if __name__ == '__main__':
    sys.exit(main())
