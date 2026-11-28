# QR Code Generator

**Tired of ads? Here, use this instead.**

Application code written entirely by AI under the direction of **Jirawat Pratuangtip**. See the [disclaimer](#disclaimer).

A local, ad-free QR design app for Windows and Android, with a Python launcher for macOS. Customize your QR, preview it live, and export files without an account or expiring redirect links.

## Downloads

Get compiled apps from [GitHub Releases](https://github.com/Jirawat2105/QR-Code-Generator/releases). GitHub source archives contain project files, not the compiled application.

| Platform | Download |
| --- | --- |
| Windows x64 — EXE or Python | [ZIP with EXE and auto-installing run.bat](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.2.0/QRGenerator-1.2.0-Windows.zip) |
| macOS — Python only | [ZIP with one-click Run.command](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.2.0/QRGenerator-1.2.0-macOS-Python.zip) |
| Android ARM64 phones | [APK, approximately 29 MB](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.2.0/QRGenerator-1.2.0-Android-arm64-v8a.apk) |
| Android x86_64 / emulator | [APK](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.2.0/QRGenerator-1.2.0-Android-x86_64.apk) |

The macOS download contains Python source and a launcher, with no compiled app or DMG. Native macOS GUI behavior has not been validated on a Mac.

## Getting started

**Windows:** Extract the entire ZIP, then open `QRGenerator.exe`. Keep `_internal` beside the executable. Python is included; do not copy the EXE alone.

**Windows Python alternative:** Double-click `run.bat` in the same extracted folder. It automatically installs Python 3.13 if a compatible interpreter is missing, installs the app dependencies into `.python-env`, and opens the app. There is no separate setup step. This route uses `src/main.py` and does not invoke the bundled `QRGenerator.exe` or its `_internal` runtime.

**macOS Python:** Extract the macOS Python ZIP into a writable folder, then double-click **Run.command**. It selects Apple Silicon or Intel setup tools, automatically installs Python 3.13 if needed, installs dependencies, and starts the Python app. No DMG, Homebrew, Xcode, or administrator installation is needed.

Both Python launchers need internet access on the first run, including Flet's initial desktop-client download. After a successful first launch, they reuse the interpreter, dependencies and desktop client and can work offline. Keep the launcher, `requirements.txt`, `src`, and (on Windows) `scripts` together. Setup uses a version-pinned, SHA-256-verified [uv download](https://docs.astral.sh/uv/getting-started/installation/) and its [automatic Python provisioning](https://docs.astral.sh/uv/guides/install-python/); existing global Python packages and PATH are left alone. Missing dependencies are installed before the app starts. The app still uses Flet's native desktop client; system security policy can also block downloaded Python or third-party components.

**Android:** Install the APK matching your architecture. Most modern phones use ARM64. Android 17 was tested using an API 37 x86_64 emulator with 16 KB memory pages; physical ARM64 phones have not been tested. Both APKs have 16 KB-aligned native libraries. The build uses minimum SDK 24 and target SDK 36.

Enter an HTTP/HTTPS URL, customize the design, and select **Export QR code** or **Export all formats (.zip)**.

## Features

- Clean dark interface with live vector previews.
- Collapsible setting sections; the chevron leaves only the heading visible without resetting values.
- Red Clear URL button inside the URL field; an empty URL blocks export.
- Optional Advanced color pickers for ink and background: hue strip, saturation/brightness square, HEX/RGB/HSV entry, current/new swatches, Apply and Cancel. Choose Advanced in the corresponding color-picker dropdown to open it. Plain/Gradient styles and background opacity remain independent.
- Preview on the left and Customize on the right on Windows and Android landscape; scrolling portrait layout on Android.
- Square, Square Rounded (separate softly rounded cells), Octagon, Hexagon, dotted, diamond, and horizontal body shapes; selectable eye frames and eye balls.
- Plain or gradient ink; solid, gradient, or image backgrounds with opacity, rounding, and soft edges.
- Optional logo with width/height percentage scaling. Oversized logos auto-fit without stretching or cropping.
- Optional reserved logo space with adjustable padding.
- Minimalist mode keeps customization enabled, using fewer modules where possible.
- Windows Tab and Android double-space URL completion with `https://`.
- Custom resolution from 256 to 8192 pixels.
- PNG, SVG, PDF, JPG, or all formats in a ZIP.
- Click the app icon for creator credits.

## Output quality and limitations

| Format | Behavior |
| --- | --- |
| PNG | Lossless raster with transparency support. |
| SVG | Vector QR geometry with embedded background effects and logo images. |
| PDF | Raster image at the selected resolution, placed in a 300 dpi document with a white transparency matte. |
| JPG | Re-encoded at quality 97 with a white transparency matte; not lossless. |

The four-module quiet zone, finder patterns and timing structure are retained. A reserved logo area may cover central alignment markers; the app warns when this happens. With a logo, Regular uses error correction H and Minimalist uses Q. Styling, large logos, low contrast, transparent backgrounds, and photographs can reduce scan reliability. The app shows design feedback, but no artistic design is guaranteed to scan. Check the exported file and a printed sample before relying on it.

Logo percentages refer to the QR area excluding its four-module quiet zone. Scale can be set from 5–80% using Width or Height. Standard auto-fit limits the longest side to 25%. Enable **Wide wordmark** to span the center: it limits the short dimension to 25% and keeps artwork eight modules from each QR edge to protect timing/finder bands. Both modes preserve the ratio and report the effective scale. Input images are limited to 16 MB and 25 megapixels; imported assets are proportionally normalized to at most 2048 pixels per side.

For a look like the supplied wordmark reference, choose **Square Rounded** for Body, Eye frame and Eye ball, plain black ink, a plain white background at 100% opacity, background rounding 0, and edge blur 0. Import the original wide logo image, enable **Wide wordmark**, use Width around 65–70%, enable reserved space and start with 1 module of padding. URL length changes the module layout; test the final export before printing.

Minimalist stays enabled with or without artwork: it uses error correction M without a logo and Q with a logo; Regular uses H. The preview shows the active mode, actual grid size and Regular grid size for comparison. Some URLs fit the same grid size at both levels; the selected mode still applies. Default logo padding is 1 module. Large logos/padding may require Regular mode for reliable scanning. Settings are session-only and are not automatically restored after closing the app or Android activity recreation.

## Performance and privacy

Rendering happens locally. The app encodes the supplied URL directly; it does not need to visit the destination to generate a QR.

Flutter Canvas draws the vector preview and gradient shader, with Impeller enabled on Android for GPU rendering where supported. File exports use the CPU/Pillow renderer. Windows uses up to two worker processes. Android uses up to four worker threads for native image operations; pure Python stages remain limited by the GIL. GPU export acceleration and physical-device performance benchmarks are not claimed.

APKs are split by CPU architecture and use compressed native libraries. The ARM64 APK is approximately 81% smaller than the earlier universal package; installed size is larger than the compressed download.

## Repository layout

```text
src/main.py       Application entry point
src/qrstudio/     UI, QR renderer, GPU preview, URL shortcuts, workers
src/assets/       App icons
scripts/          Build, packaging, and E2E tools
tests/            Engine regression tests
```

Compiled downloads belong in Releases, not the source tree. Build directories, virtual environments, emulator images, and test outputs are excluded from Git.

## Run from source

On Windows, double-click `run.bat`. On macOS, double-click `Run.command`. Both install Python 3.13 automatically when needed and install their own runtime dependencies. `setup.bat` remains available as an optional Windows install-only shortcut; `Run.command --prepare-only` does the same on macOS.

If you already have Python 3.13 and prefer manual setup:

```sh
python3.13 -m venv .python-env
# macOS:
.python-env/bin/python -m pip install -r requirements.txt
.python-env/bin/python src/main.py
```

On Windows, use `py -3.13 -m venv .python-env`, then `.python-env\Scripts\python.exe` for the two subsequent commands. Developer/build dependencies are separate from these runtime requirements.

Alternatively:

```powershell
uv sync --dev
uv run flet run src/main.py
```

## Build from source

Windows:

```powershell
powershell -File scripts/build_windows.ps1
```

Android (requires Flutter, Android SDK, and JDK; Flet can provision build tools):

```powershell
uv run flet build apk --yes
```

Windows output: `dist/QRGenerator/`. Android output: `build/apk/QRGenerator-arm64-v8a.apk` and `QRGenerator-x86_64.apk`.

To collect versioned release files and SHA-256 checksums after both builds:

```powershell
uv run python scripts/package_release.py
```

Keep the Android signing key used for your distribution to sign compatible future updates. Never commit signing credentials.

## Testing

```powershell
uv sync --dev
uv run python scripts/check.py
```

This runs engine regression tests and an actual Flet UI E2E session in Microsoft Edge, including real uploads/downloads and independent QR decoding from PNG/JPG/SVG/PDF and GPU-preview screenshots. It checks portrait and landscape layouts, URL completion, Credits, Minimalist customization, and logo auto-fit.

After building Windows, run `uv run python scripts/check.py --packaged` to drive the same full E2E suite against the actual packaged EXE through its local web transport.

With an Android emulator running and `adb` available:

```powershell
uv run python scripts/e2e_android.py
```

Set `ANDROID_SERIAL` when multiple devices are connected. The native workflow validates installation, URL entry, actual logo import through Android Files, Square Rounded shape selection, intact logo pixels, system Save dialogs, all-format ZIP export, and emulator rotation. `scripts/e2e_safe_area.py` additionally checks simulated cutouts on a dedicated QA emulator.

Release 1.2.0 passed 139 engine tests, 22 packaged Windows UI E2E scenarios through local web transport, 21 native Android 17 scenarios (API 37, 16 KB pages), and two simulated cutouts. It includes raw hue/SV gestures, HEX/RGB/HSV entry, Apply/Cancel, collapsed invalid settings, polygon previews/exports and resizing an open picker. Prior Minimalist/logo regressions still independently decode actual QR data, grid size and error-correction level from previews and PNG/JPG/SVG/PDF exports. See the release QA report for exact scenario counts and platform limits. Physical phones, physical printing, and macOS were not tested.

The **2026-11-28 packaging refresh** adds Windows/macOS Python launchers without changing the app renderer, Windows EXE or Android APKs. Its checks reran **139 engine tests** and **22 real Flet UI E2E scenarios against `run.bat` from the extracted ZIP**, with Python absent from PATH, an empty managed-Python/cache directory, and the bundled EXE unavailable. It also checked offline reuse, automatic repair of a removed dependency, and stopping on install failure. A native Windows smoke check observed the dark UI, live QR and functioning Minimalist toggle after the automatic Flet-client download. macOS checks cover shell syntax, executable ZIP permissions, both official setup archive hashes and binary-wheel dependency resolution for Intel/Apple Silicon; native Mac GUI behavior remains untested. See `QA-LAUNCHERS-1.2.0.json` in Releases.

To repeat the Windows launcher workflow after packaging:

```powershell
uv run python scripts/e2e_launchers.py
```

This downloads a fresh, isolated Python and dependencies into `.qa`, then drives the actual app with `scripts/e2e_web.py`. It does not uninstall or change your system Python.

## Troubleshooting

- Extract the Windows ZIP fully and keep `_internal` beside the EXE.
- For the Windows Python route, open `run.bat`; read any setup error in its console before closing. Retry after restoring internet access if the first download fails. Do not disable antivirus to run the app.
- If macOS refuses to open `Run.command`, use **Open** from its context menu when permitted by your Mac's policy. If the executable bit was lost while copying, open Terminal in the extracted folder and run `chmod +x Run.command`, then `./Run.command`. You can also run `bash Run.command` directly. Setup errors stay visible in Terminal.
- Use the correct APK architecture and ensure sufficient installation space.
- Check the URL and displayed settings if export is disabled.
- If scanning fails, use darker ink, a light plain background, a smaller logo, or a higher resolution.
- Check file/folder permissions and available disk space if saving fails.

## Disclaimer

QR Generator's application code was written entirely by AI under the direction of **Jirawat Pratuangtip**. Third-party libraries are separate projects maintained by their respective authors.

AI-generated code may contain bugs or unexpected behavior. This software is provided "as is", without warranty, under the terms of the [MIT License](LICENSE). Keep backups of important images and verify exported results before relying on them.

### Unsigned Windows executable

The distributed Windows executable is not digitally signed. Windows may display **Unknown Publisher**, and Windows or your browser may show additional warnings. See [Microsoft's explanation of SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

Unknown Publisher means the executable lacks a trusted publisher signature. That message alone is not a malware detection and does not establish that a file is safe. Investigate any specific threat detection before running the file. Download from [this repository](https://github.com/Jirawat2105/QR-Code-Generator) or its Releases; source is available for inspection and rebuilding.

## Built with

- Python and Flet / Flutter
- qrcode and Pillow
- PyInstaller for Windows packaging
- Flet tooling for Android packaging

Third-party dependencies retain their own licenses.

## Author

Project creator: **Jirawat Pratuangtip**. Application code written entirely by AI under their direction.

GitHub: [Jirawat2105](https://github.com/Jirawat2105)

## License

Copyright (c) 2026 Jirawat Pratuangtip.

Project code is licensed under the [MIT License](LICENSE). Third-party dependencies retain their own licenses.

[Thai usage and build notes](README_TH.md)
