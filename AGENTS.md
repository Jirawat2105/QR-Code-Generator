# MuPhoto QR Studio

- Python + Flet application; Windows desktop and installable Android APK are both in scope.
- Preserve the original logo aspect ratio. The user chooses whether its width or height defines the percentage scale.
- Keep URL entry required, and block export while any displayed setting is invalid or preview is stale.
- Keep rendering off the UI thread; use bounded processes on Windows and the portable thread fallback on Android.
- Always run E2E after changes. Run engine regression tests and `scripts/e2e_web.py` against the actual Flet app. Test actual exports and decode generated QR files; mocks alone do not establish E2E coverage.
- For Android changes, build the APK and run the native emulator workflow in `scripts/e2e_android.py` when the SDK/emulator is available. Report any untested physical-device behavior honestly.
- Never imply that every artistic customization will scan. Show contrast/background/large-logo feedback and retain the quiet zone and functional modules.
- SVG QR geometry is vector; background effects and uploaded artwork are embedded images. PDF is a 300 dpi raster document with white matte for alpha, also shown in the UI.
