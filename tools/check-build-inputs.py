"""Check Madeira's Xcode file references before scheduling a Mac build.

This is a file-presence check, not a compiler, linker or device compatibility test.
It intentionally fails if this project's PBX layout becomes unsupported.
"""
import argparse
import json
from pathlib import Path
import re
import sys


def field(body, key):
    match = re.search(r'\b' + key + r'\s*=\s*("[^"]*"|[^;]+);', body)
    return match.group(1).strip().strip('"') if match else None


def inspect(root):
    project = root / 'app/Madeira.xcodeproj/project.pbxproj'
    text = re.sub(r'/\*.*?\*/', '', project.read_text(encoding='utf-8'), flags=re.S)
    objects = dict(re.findall(r'\b([A-F0-9]{8,24})\s*=\s*\{([^{}]*)\};', text, re.S))
    groups = {key: body for key, body in objects.items() if field(body, 'isa') == 'PBXGroup'}
    parents = {}
    for key, body in groups.items():
        children = re.search(r'children\s*=\s*\((.*?)\);', body, re.S)
        if not children:
            raise ValueError(f'Group {key} has no children list')
        for child in re.findall(r'\b[A-F0-9]{8,24}\b', children.group(1)):
            if child in parents:
                raise ValueError(f'Multiple parents for {child}')
            parents[child] = key

    def group_path(key, seen=()):
        if key in seen:
            raise ValueError('Cycle in Xcode groups')
        body = groups[key]
        if field(body, 'sourceTree') != '<group>':
            raise ValueError(f'Unsupported group sourceTree: {key}')
        base = group_path(parents[key], seen + (key,)) if key in parents else root / 'app'
        return base / (field(body, 'path') or '')

    checks = []
    for key, body in objects.items():
        if field(body, 'isa') != 'PBXFileReference':
            continue
        tree, path = field(body, 'sourceTree'), field(body, 'path')
        if tree in ('SDKROOT', 'BUILT_PRODUCTS_DIR'):
            continue
        if tree != '<group>' or key not in parents or not path:
            raise ValueError(f'Unsupported file reference: {key}')
        target = (group_path(parents[key]) / path).resolve()
        try:
            relative = target.relative_to(root.resolve()).as_posix()
        except ValueError:
            checks.append(dict(path=path, status='outside_repository'))
            continue
        status = 'present' if target.exists() else 'missing'
        try:
            if target.is_file():
                if target.stat().st_size == 0:
                    status = 'empty'
                elif target.suffix == '.a':
                    with target.open('rb') as stream:
                        magic = stream.read(8)
                    if magic != b'!<arch>\n' and magic[:4] not in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
                        status = 'invalid_archive'
        except OSError:
            status = 'missing'
        checks.append(dict(path=relative, status=status))
    if not checks:
        raise ValueError('No project inputs parsed')
    # These directories are copied wholesale by Xcode, so a present but empty
    # directory is not enough to launch Wine or a DirectX 11 workload.
    for relative in (
        'app/Madeira/arm64ec-windows/ntdll.dll',
        'app/Madeira/arm64ec-windows/xtajit64.dll',
        'app/Madeira/aarch64-windows/ntdll.dll',
        'app/Madeira/aarch64-windows/d3d11.dll',
        'app/Madeira/aarch64-windows/dxgi.dll',
        'app/Madeira/x86_64-vcruntime/msvcp140.dll',
        'app/Madeira/x86_64-vcruntime/vcruntime140.dll',
        'app/Madeira/x86_64-vcruntime/vcruntime140_1.dll',
    ):
        p = root / relative
        try:
            ok = p.is_file() and p.stat().st_size > 0
        except OSError:
            ok = False
        checks.append(dict(path=relative, status='present' if ok else 'missing'))
    return dict(scope='project input presence only; compile and device tests still required',
                ready_for_compile_attempt=all(c['status'] == 'present' for c in checks), checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = inspect(args.root)
    except (OSError, ValueError) as error:
        print(f"check-build-inputs failed: {error}", file=sys.stderr)
        return 2
    try:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except OSError as error:
        print(f"Failed to write output {args.output}: {error}", file=sys.stderr)
        return 2
    for check in report['checks']:
        if check['status'] != 'present':
            hint = ""
            if "x86_64-vcruntime" in check['path']:
                hint = " (fetch via tools/fetch-vcruntime.md or dummy via tools/ensure-ci-placeholders.sh)"
            elif check['path'].endswith(".a"):
                hint = " (build via GH workflow or dummy via ensure-ci-placeholders.sh)"
            print(f"{check['status']}: {check['path']}{hint}")
    print(f"Checked {len(report['checks'])} inputs. Compile-attempt prerequisites: "
          + ('present' if report['ready_for_compile_attempt'] else 'INCOMPLETE'))
    if not report['ready_for_compile_attempt']:
        print("Hint: for CI validation without long builds, run: bash tools/ensure-ci-placeholders.sh")
    return 0 if report['ready_for_compile_attempt'] else 1


if __name__ == '__main__':
    sys.exit(main())
