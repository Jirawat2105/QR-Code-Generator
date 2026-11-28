"""Collect already-built artifacts without modifying either build workspace."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"dist"
VERSION="1.2.0"


def source_files():
    """Only app source/assets, never local environments or bytecode."""
    return [p for p in sorted((ROOT/"src").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]


def add_file(archive, path, relative):
    # Windows-created ZIPs must still give Finder an executable, LF shell script.
    info=zipfile.ZipInfo(str(relative).replace("\\", "/"))
    info.create_system=3
    info.external_attr=(0o100755 if path.suffix==".command" else 0o100644)<<16
    data=path.read_bytes()
    if path.suffix==".command":
        data=data.replace(b"\r\n", b"\n")
    elif path.suffix==".bat":
        data=data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=4)


def main():
    windows=DIST/"QRGenerator"
    assert (windows/"QRGenerator.exe").exists(),"Build Windows first."
    (windows/"START-HERE.txt").write_text(
        f"QR Generator {VERSION}\n\n"
        "Open QRGenerator.exe to start. No Python installation is required.\n"
        "Keep the _internal folder beside the EXE. Extract the whole ZIP before opening.\n\n"
        "PYTHON ALTERNATIVE: double-click run.bat instead of the EXE.\n"
        "It installs Python 3.13 if missing, installs dependencies, and opens the same app.\n"
        "First setup needs internet access. No Administrator privileges are needed.\n"
        "Keep src, scripts and requirements.txt beside run.bat. No separate setup step.\n"
        "The Python route does not call QRGenerator.exe or use _internal.\n\n"
        "Enter a full http/https URL. Use the red X to clear it. Choose shapes, colors and an optional logo.\n"
        "Collapse setting sections with their arrows. Choose Advanced in the ink/background color picker for HSV/RGB/HEX.\n"
        "Logo scale can reference Width or Height, preserving original proportions.\n"
        "Oversized logos automatically fit inside a safe center area.\n"
        "Tab completes https:// in the URL field. Minimalist keeps all styles editable, including with a logo.\n"
        "Click the app icon for Credits: Jirawat Pratuangtip / github.com/Jirawat2105.\n"
        "Export PNG, SVG, PDF, JPG, or all four in a ZIP.\n"
        "PNG/SVG support transparency; JPG/PDF use a white matte.\n"
        "QR geometry in SVG is vector; PDF contains a 300 dpi raster image.\n\n"
        "All rendering happens on your device. Test your final printed design with a phone.\n",
        encoding="utf-8")
    for name in ("LICENSE", "README.md", "README_TH.md", "run.bat", "setup.bat", "requirements.txt"):
        shutil.copy2(ROOT/name, windows/name)
    for path in [*source_files(),ROOT/"scripts/launch_windows.ps1"]:
        target=windows/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    apks=[]
    for abi in ("arm64-v8a","x86_64"):
        apk=ROOT/"build"/"apk"/f"QRGenerator-{abi}.apk"
        assert apk.exists(),f"Build Android {abi} first."
        target_apk=DIST/f"QRGenerator-{VERSION}-Android-{abi}.apk"
        shutil.copy2(apk,target_apk)
        apks.append(target_apk)
    target_zip=DIST/f"QRGenerator-{VERSION}-Windows.zip"
    with zipfile.ZipFile(target_zip,"w",zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for path in sorted(windows.rglob("*")):
            if path.is_file() and not ({".python-env","__pycache__"} & set(path.relative_to(windows).parts)):
                # The compiled runtime must retain any original executable modes.
                if "_internal" in path.relative_to(windows).parts or path.suffix==".exe":
                    z.write(path,path.relative_to(DIST))
                else:
                    add_file(z,path,path.relative_to(DIST))
    mac_zip=DIST/f"QRGenerator-{VERSION}-macOS-Python.zip"
    with zipfile.ZipFile(mac_zip,"w") as z:
        for path in [*source_files(),*[ROOT/name for name in ("Run.command","requirements.txt","LICENSE","README.md","README_TH.md")]]:
            add_file(z,path,Path("QRGenerator")/path.relative_to(ROOT))
        z.writestr("QRGenerator/START-HERE.txt",
                   "QR Generator - macOS Python edition\n\n"
                   "Extract the ZIP into a writable folder and double-click Run.command.\n"
                   "It downloads Python 3.13 if missing, installs dependencies and opens the app.\n"
                   "First setup needs internet. No DMG, Homebrew, Xcode or sudo is required.\n"
                   "Apple Silicon and Intel setup downloads are selected automatically.\n"
                   "If Finder denies execution, see the macOS troubleshooting steps in README.md.\n"
                   "Keep Run.command, requirements.txt and src together.\n"
                   "Native macOS GUI behavior has not been tested on a physical Mac.\n")
    report=[]
    for path in (target_zip,mac_zip,*apks):
        h=hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):
                h.update(block)
        report.append({"file":path.name,"bytes":path.stat().st_size,"sha256":h.hexdigest()})
    (DIST/"SHA256SUMS.txt").write_text("\n".join(f"{r['sha256']}  {r['file']}" for r in report)+"\n",encoding="ascii")
    (DIST/"release.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
