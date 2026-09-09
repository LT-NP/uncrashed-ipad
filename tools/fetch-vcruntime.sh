#!/bin/bash
# Fetch Microsoft VC++ runtime DLLs (unmodified) for local use.
# See tools/fetch-vcruntime.md for license notes. DLLs are NOT committed.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/app/Madeira/x86_64-vcruntime"
URL="${VCRUNTIME_URL:-https://aka.ms/vs/17/release/vc_redist.x64.exe}"
TMP="/tmp/vc_redist.x64.exe"
CAB="/tmp/vcredist_cab"

echo "Downloading $URL -> $TMP"
if command -v curl >/dev/null; then curl -L -o "$TMP" "$URL"
elif command -v wget >/dev/null; then wget -O "$TMP" "$URL"
else echo "Need curl or wget"; exit 1; fi

if ! command -v 7zz >/dev/null && ! command -v 7z >/dev/null; then
  echo "Installing 7zip..."
  if command -v brew >/dev/null; then brew install sevenzip
  else echo "Install 7zip manually (7zz)"; exit 1; fi
fi
SEVEN="7zz"; command -v 7zz >/dev/null || SEVEN="7z"

echo "Extracting VC_redist..."
mkdir -p "$CAB" "$OUT"
"$SEVEN" x "$TMP" -o"$CAB" -y >/dev/null
# CAB inside .rsrc/1033/CABINET/*.cab - layout varies
CABFILE=$(find "$CAB" -name "*.cab" | head -n 1)
if [[ -z "$CABFILE" ]]; then echo "CAB not found under $CAB"; find "$CAB" | head -n 20; exit 1; fi
"$SEVEN" x "$CABFILE" -o"$OUT" -y >/dev/null

# Verify 12 expected files exist and have Authenticode signature
echo "Verifying DLLs in $OUT:"
python3 - "$OUT" <<'PY'
import struct, sys, pathlib
out = pathlib.Path(sys.argv[1])
expected = ["concrt140.dll","msvcp140.dll","msvcp140_1.dll","msvcp140_2.dll","msvcp140_atomic_wait.dll","msvcp140_codecvt_ids.dll","vcamp140.dll","vccorlib140.dll","vcomp140.dll","vcruntime140.dll","vcruntime140_1.dll","vcruntime140_threads.dll"]
for name in expected:
    p = out / name
    if not p.is_file():
        print(f"missing {name}")
        continue
    d = p.read_bytes()
    try:
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        off, size = struct.unpack_from('<II', d, pe + 24 + 112 + 4*8)
        ok = size != 0 and off + size <= len(d)
        print(f"{'signed' if ok else 'UNSIGNED'} {p} ({len(d)} bytes)")
        if not ok:
            print(f"  WARNING: {name} appears unsigned/truncated — must be unmodified per Microsoft terms")
    except Exception as e:
        print(f"error checking {name}: {e}")
PY

echo "Done. DLLs in $OUT (gitignored, not for redistribution)."
echo "Clean up: rm -rf $CAB $TMP"
