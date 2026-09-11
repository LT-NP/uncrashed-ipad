"""Verify a transferred Uncrashed tree against an audit manifest; Python stdlib only.

Implements the POST_BUILD_ROADMAP §5 completion check on any machine with
the source manifest (made where the game is installed) and the destination
tree (a copy of it): every manifest file must exist with a matching size,
manifest-hashed files must match by sha256, the shipping executable must be
present at its expected relative path, and the destination must not contain
a second nested game directory (the classic double-copy mistake).

An executable alone does not prove the transfer completed — this compares
counts and sizes, plus hashes where the manifest carries them. Exit 0 only
when nothing is missing or mismatched.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

EXE_REL = 'Uncrashed/Binaries/Win64/Uncrashed-Win64-Shipping.exe'


def sha256_of(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def collect_dest(dest):
    """Map relative posix path -> absolute Path for files; list nested dups."""
    found, nested_dup = {}, []
    try:
        dest_name = dest.resolve().name.casefold()
    except OSError:
        dest_name = dest.name.casefold()
    for p in dest.rglob('*'):
        try:
            if p.is_dir():
                if p.name.casefold() == dest_name:
                    found_rel = p.relative_to(dest).as_posix()
                    nested_dup.append(found_rel)
                continue
            if p.is_file():
                found[p.relative_to(dest).as_posix()] = p
        except OSError:
            continue
    return found, nested_dup


def verify(manifest, dest, check_hashes=False):
    """Compare manifest against dest. Returns (ok, result-dict)."""
    expected = manifest.get('files', [])
    limit = manifest.get('hash_limit_mb', 64) * 1024 * 1024
    found, nested_dup = collect_dest(dest)
    missing, size_mismatched, hash_mismatched = [], [], []
    bytes_expected = sum(e.get('size', 0) for e in expected)
    bytes_found = 0
    for entry in expected:
        rel = entry.get('path', '')
        want = entry.get('size', 0)
        p = found.get(rel)
        if p is None:
            missing.append(rel)
            continue
        try:
            got = p.stat().st_size
        except OSError:
            missing.append(rel)
            continue
        bytes_found += got
        if got != want:
            size_mismatched.append(dict(path=rel, expected=want, actual=got))
            continue
        digest = entry.get('sha256')
        if digest and (check_hashes or want <= limit):
            try:
                actual = sha256_of(p)
            except OSError:
                missing.append(rel)
                continue
            if actual != digest:
                hash_mismatched.append(rel)
    extras = sorted(set(found) - {e.get('path', '') for e in expected})
    exe_present = EXE_REL in found and EXE_REL not in set(missing)
    ok = not missing and not size_mismatched and not hash_mismatched \
        and not nested_dup and exe_present
    result = dict(
        scope='transfer presence/size/hash comparison only; runtime tests still required',
        ok=ok,
        expected_files=len(expected),
        expected_bytes=bytes_expected,
        matched_bytes=bytes_found,
        missing=sorted(missing),
        size_mismatched=size_mismatched,
        hash_mismatched=sorted(hash_mismatched),
        nested_duplicate_dirs=sorted(nested_dup),
        exe_present=exe_present,
        extra_files=len(extras),
    )
    return ok, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--check-hashes', action='store_true',
                        help='Hash even files above the manifest hash limit (slow)')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f"Failed to read manifest: {e}", file=sys.stderr)
        return 2
    if manifest.get('version') != 1:
        print(f"Unsupported manifest version: {manifest.get('version')}", file=sys.stderr)
        return 2
    ok, result = verify(manifest, args.dest, args.check_hashes)
    if args.output is not None:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        except OSError as e:
            print(f"Failed to write output {args.output}: {e}", file=sys.stderr)
            return 2
    print(f"expected={result['expected_files']} files / {result['expected_bytes']} bytes; "
          f"missing={len(result['missing'])} size_mismatch={len(result['size_mismatched'])} "
          f"hash_mismatch={len(result['hash_mismatched'])} nested_dup={result['nested_duplicate_dirs']} "
          f"exe={result['exe_present']} extras={result['extra_files']} -> {'OK' if ok else 'INCOMPLETE'}")
    for rel in result['missing'][:20]:
        print(f"missing: {rel}")
    for m in result['size_mismatched'][:20]:
        print(f"size: {m['path']} expected={m['expected']} actual={m['actual']}")
    for rel in result['hash_mismatched'][:20]:
        print(f"hash: {rel}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
