# QR Code Generator

**Tired of ads? Here, use this instead.**

Application code written entirely by AI under the direction of **Jirawat Pratuangtip**. See the [disclaimer](#disclaimer).

A local, ad-free QR design app for Windows and Android. Customize your QR, preview it live, and export files without an account or expiring redirect links.

## Downloads

Get compiled apps from [GitHub Releases](https://github.com/Jirawat2105/QR-Code-Generator/releases). GitHub source archives contain project files, not the compiled application.

| Platform | Download |
| --- | --- |
| Windows x64 | [QR Generator 1.1.0 ZIP](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.1.0/QRGenerator-1.1.0-Windows.zip) |
| Android ARM64 phones | [APK, approximately 29 MB](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.1.0/QRGenerator-1.1.0-Android-arm64-v8a.apk) |
| Android x86_64 / emulator | [APK](https://github.com/Jirawat2105/QR-Code-Generator/releases/download/v1.1.0/QRGenerator-1.1.0-Android-x86_64.apk) |

No compiled macOS app is available. macOS has not been built or validated for this release.

## Getting started

**Windows:** Extract the entire ZIP, then open `QRGenerator.exe`. Keep `_internal` beside the executable. Python is included; do not copy the EXE alone.

**Android:** Install the APK matching your architecture. Most modern phones use ARM64. Android 17 was tested using an API 37 x86_64 emulator with 16 KB memory pages; physical ARM64 phones have not been tested. Both APKs have 16 KB-aligned native libraries. The build uses minimum SDK 24 and target SDK 36.

Enter an HTTP/HTTPS URL, customize the design, and select **Export QR code** or **Export all formats (.zip)**.

## Features

- Clean dark interface with live vector previews.
- Preview on the left and Customize on the right on Windows and Android landscape; scrolling portrait layout on Android.
- Square, rounded, dotted, diamond, and horizontal body shapes; selectable eye frames and eye balls.
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

The quiet zone and functional QR structure are retained. Styling, large logos, low contrast, transparent backgrounds, and photographs can reduce scan reliability. The app shows design feedback, but no artistic design is guaranteed to scan. Check the exported file and a printed sample before relying on it.

Logo percentages refer to the QR area excluding its four-module quiet zone. Auto-fit limits the longest logo dimension to 25% of that area and reports the effective scale. Input images are limited to 16 MB and 25 megapixels; imported assets are proportionally normalized to at most 2048 pixels per side.

Minimalist mode uses error correction M without a logo and H with a logo; regular mode uses H. Settings are session-only and are not automatically restored after closing the app or Android activity recreation.

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

Use 64-bit Python 3.13. On Windows, run `setup.bat`, then `run.bat`. Initial dependency installation requires internet access.

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

With an Android emulator running and `adb` available:

```powershell
uv run python scripts/e2e_android.py
```

Set `ANDROID_SERIAL` when multiple devices are connected. The native workflow validates installation, URL entry, system Save dialogs, all-format ZIP export, and emulator rotation. `scripts/e2e_safe_area.py` additionally checks simulated cutouts on a dedicated QA emulator.

Release 1.1.0 passed 42 engine tests, 12 packaged Windows web-transport E2E scenarios, 10 native Android 17 scenarios, and two cutout layouts. Physical phones, physical printing, and macOS were not tested.

## Troubleshooting

- Extract the Windows ZIP fully and keep `_internal` beside the EXE.
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
