# Obtaining the Microsoft Visual C++ runtime DLLs

Madeira needs twelve unmodified Microsoft x64 runtime DLLs for Uncrashed.
They are separate from this project's source license and are gitignored.

## Fetch and extract

Install Python 3, curl and 7-Zip (`brew install sevenzip` on macOS), then run:

```sh
bash tools/fetch-vcruntime.sh
```

The script downloads the official [Visual Studio 2022 x64 redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).
Microsoft documents its downloads on the [Visual C++ redistributable page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).
The script writes these files to `app/Madeira/x86_64-vcruntime/`:

```text
concrt140.dll              msvcp140_codecvt_ids.dll   vcruntime140.dll
msvcp140.dll               vcamp140.dll               vcruntime140_1.dll
msvcp140_1.dll             vccorlib140.dll            vcruntime140_threads.dll
msvcp140_2.dll             vcomp140.dll
msvcp140_atomic_wait.dll
```

For an already downloaded official installer, including offline use:

```sh
VCRUNTIME_INSTALLER=/path/to/VC_redist.x64.exe bash tools/fetch-vcruntime.sh
```

`VCRUNTIME_OUT` overrides the destination. `VCRUNTIME_URL` overrides the HTTPS
download URL. The installer and DLL SHA-256 hashes are printed for comparison
between builds; the moving Microsoft URL is not a version pin.

The helper locates all embedded CAB containers, including the attached payload
after the WiX Burn user interface CAB. It recursively extracts CAB/MSI payloads
and converts names such as `msvcp140.dll_amd64` to `msvcp140.dll` without changing
their contents. The x64 redistributable also includes ARM64 files; those are not
substitutes for the x64 runtime needed by the game.

Extraction fails if any expected file is absent, malformed, the wrong
architecture, conflicting, or missing its complete certificate table. Validation
finishes before the existing runtime DLLs are replaced. Temporary extraction
directories are removed automatically.

## Validation and terms

The PE and certificate checks detect placeholders, truncated sections and
stripped signatures. They do **not** verify the cryptographic signature or its
trust chain, and a certificate payload alone does not prove who published a file.
Use the official Microsoft installer. Never strip or patch these DLLs.

These binaries are not covered by Madeira's source license. Any redistribution
must follow the applicable Microsoft terms; see Microsoft's
[redistribution documentation](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files).

Regression tests can be run without downloading the runtime:

```sh
python3 -m unittest discover -s tools -p 'test_extract_vcruntime.py' -v
```
