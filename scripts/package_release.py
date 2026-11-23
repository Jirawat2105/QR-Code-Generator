"""Collect already-built artifacts without modifying either build workspace."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/"dist"
VERSION="1.1.0"


def main():
    windows=DIST/"QRGenerator"
    assert (windows/"QRGenerator.exe").exists(),"Build Windows first."
    (windows/"START-HERE.txt").write_text(
        "QR Generator 1.1.0\n\n"
        "Open QRGenerator.exe to start. No Python installation is required.\n"
        "Keep the _internal folder beside the EXE. Extract the whole ZIP before opening.\n\n"
        "Enter a full http/https URL. Choose your shapes, colors and optional logo.\n"
        "Logo scale can reference Width or Height, preserving original proportions.\n"
        "Oversized logos automatically fit inside a safe center area.\n"
        "Tab completes https:// in the URL field. Minimalist keeps all styles editable.\n"
        "Click the app icon for Credits: Jirawat Pratuangtip / github.com/Jirawat2105.\n"
        "Export PNG, SVG, PDF, JPG, or all four in a ZIP.\n"
        "PNG/SVG support transparency; JPG/PDF use a white matte.\n"
        "QR geometry in SVG is vector; PDF contains a 300 dpi raster image.\n\n"
        "All rendering happens on your device. Test your final printed design with a phone.\n",
        encoding="utf-8")
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
            if path.is_file():
                z.write(path,path.relative_to(DIST))
    report=[]
    for path in (target_zip,*apks):
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
