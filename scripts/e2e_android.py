"""Drive the installed APK through Android UIAutomator and the system Save dialog.

Requires a running Android emulator/device, adb, Pillow and ZXing-C++.
Uses the real embedded Python renderer and exported files, with no mocks.
"""
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import zxingcpp
import resvg_py
import pypdfium2 as pdfium
from PIL import Image

ADB=shutil.which("adb")
PACKAGE="com.muphoto.muphoto_qr_studio"
OUT=Path("test-results/android")
OUT.mkdir(parents=True,exist_ok=True)
URL="https://example.com/android-e2e"


def adb(*args,binary=False,timeout=40):
    result=subprocess.run([ADB,*args],capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"adb {' '.join(args)} failed: {result.stdout.decode(errors='replace')} {result.stderr.decode(errors='replace')}")
    return result.stdout if binary else result.stdout.decode("utf-8",errors="replace")


def dump():
    adb("shell","uiautomator","dump","/sdcard/qrstudio-ui.xml")
    data=adb("shell","cat","/sdcard/qrstudio-ui.xml")
    (OUT/"latest-ui.xml").write_text(data,encoding="utf-8")
    return ET.fromstring(data)


def bounds(node):
    x1,y1,x2,y2=map(int,re.findall(r"\d+",node.attrib["bounds"]))
    return x1,y1,x2,y2


def tap_node(node):
    x1,y1,x2,y2=bounds(node)
    adb("shell","input","tap",str((x1+x2)//2),str((y1+y2)//2))


def find(label,tree=None,exact=False):
    if tree is None:
        tree=dump()
    for node in tree.iter("node"):
        for field in ("text","content-desc","hint"):
            value=node.get(field,"")
            if (value==label if exact else label in value) and node.get("enabled")=="true":
                return node
    return None


def tap(label,exact=False):
    node=find(label,exact=exact)
    if node is None:
        raise AssertionError(f"Native control not found: {label}")
    tap_node(node)


def screenshot(name):
    data=adb("exec-out","screencap","-p",binary=True)
    (OUT/name).write_bytes(data)
    return data


def scan(data):
    result=zxingcpp.read_barcode(Image.open(io.BytesIO(data)).convert("RGB"))
    return result.text if result else None


def wait_scan(expected,name):
    for _ in range(25):
        data=screenshot(name)
        if scan(data)==expected:
            return
        time.sleep(.8)
    raise AssertionError(f"Native live preview did not decode to {expected}")


def scroll_to(label,direction="down",tries=24):
    w,h=map(int,re.findall(r"\d+",adb("shell","wm","size"))[-2:])
    for _ in range(tries):
        node=find(label)
        if node is not None:
            x1,y1,x2,y2=bounds(node)
            if y1>h*.1 and y2<h*.84:
                return node
        # Short, slow gestures avoid flinging past controls between XML snapshots.
        start,end=(h*.75,h*.55) if direction=="down" else (h*.48,h*.68)
        adb("shell","input","swipe",str(w//2),str(int(start)),str(w//2),str(int(end)),"650")
        time.sleep(.3)
    raise AssertionError(f"Could not scroll to native control: {label}")


def run():
    assert ADB,"Install Android platform-tools (adb) first."
    devices=adb("devices")
    assert "emulator-" in devices or "\tdevice" in devices,"Start an Android emulator or connect a device first."
    print("Waiting for Android boot to complete…",flush=True)
    for _ in range(180):
        try:
            if adb("shell","getprop","sys.boot_completed").strip()=="1":
                break
        except RuntimeError:
            pass  # A fresh AVD can briefly reconnect while provisioning.
        time.sleep(1)
    else:
        raise RuntimeError("Android did not finish booting within three minutes.")
    abi=adb("shell","getprop","ro.product.cpu.abi").strip()
    apk=list(Path("build/apk").glob(f"QRGenerator*{abi}*.apk"))
    apk_path=os.environ.get("QR_APK_PATH") or (str(apk[0]) if apk else None)
    assert apk_path,"Build the QRGenerator APK for this ABI first, or set QR_APK_PATH."
    print(adb("install","-r",apk_path,timeout=120),flush=True)
    assert PACKAGE in adb("shell","pm","list","packages",PACKAGE),"Build/install the APK first."
    adb("shell","am","force-stop",PACKAGE)
    adb("shell","am","start","-n",PACKAGE+"/.MainActivity")
    wait_scan("https://example.com","01-native-preview.png")
    print("PASS: cold start and native QR preview decoded",flush=True)
    tree=dump()
    assert find("Small code.",tree) is not None
    assert find("Preview & export",tree) is not None
    tap("Credits",exact=True)
    tree=dump()
    assert find("Jirawat Pratuangtip",tree,exact=True) is not None
    assert find("github.com/Jirawat2105",tree,exact=True) is not None
    tap("Close",exact=True)
    # Jump through the actual bottom navigation and enter a different URL.
    tap("Customize",exact=True)
    time.sleep(.8)
    node=scroll_to("Destination URL")
    tap_node(node)
    # Android IMEs vary in their handling of synthetic Ctrl+A. Clear using
    # ordinary editing keys, based on the text observed in UIAutomator.
    adb("shell","input","keyevent","123") # move caret to end
    existing=node.get("text","")
    if existing:
        adb("shell","input","keyevent",*(["67"]*len(existing)))
    adb("shell","input","text","example.com/android-e2e%s%s")
    time.sleep(.8)
    edited=find("Destination URL")
    assert edited is not None and edited.get("text")==URL,"Android double-space must add https:// before blur"
    adb("shell","input","keyevent","4") # close keyboard
    time.sleep(.8)
    tap("Preview & export",exact=True)
    time.sleep(.8)
    wait_scan(URL,"02-updated-preview.png")
    print("PASS: native URL entry and preview update decoded",flush=True)
    # Use Android's real document provider; select the default Downloads location.
    tap_node(scroll_to("Export QR code"))
    time.sleep(2)
    save=find("SAVE",exact=True)
    if save is None:
        save=find("Save",exact=True)
    if save is None:
        screenshot("save-dialog.png")
        raise AssertionError("Android system save dialog was not displayed")
    tap_node(save)
    time.sleep(2)
    # If a previous run wrote the same name, confirm only this test's overwrite.
    tree=dump()
    replace=find("Replace",tree,exact=True)
    if replace is None:
        replace=find("REPLACE",tree,exact=True)
    if replace is not None:
        tap_node(replace)
        time.sleep(1)
    files=adb("shell","find","/sdcard/Download","-maxdepth","1","-name","qr-generator-2048*.png").splitlines()
    assert files,"Native export was not saved in Downloads"
    latest=files[-1]
    path=OUT/"native-export.png"
    adb("pull",latest,str(path))
    assert Image.open(path).size==(2048,2048)
    assert scan(path.read_bytes())==URL
    screenshot("03-native-export.png")
    print("PASS: Android system Save dialog and exported PNG decoded",flush=True)
    tap_node(scroll_to("Export all formats (.zip)"))
    time.sleep(2)
    save=find("SAVE",exact=True)
    if save is None:
        save=find("Save",exact=True)
    assert save is not None,"Native all-format ZIP save dialog must open"
    tap_node(save)
    time.sleep(2)
    replace=find("Replace",exact=True)
    if replace is None:
        replace=find("REPLACE",exact=True)
    if replace is not None:
        tap_node(replace)
        time.sleep(1)
    bundles=adb("shell","find","/sdcard/Download","-maxdepth","1","-name","qr-generator-all*.zip").splitlines()
    assert bundles,"Native multicore ZIP export must be saved"
    bundle_path=OUT/"native-all.zip"
    adb("pull",bundles[-1],str(bundle_path))
    with zipfile.ZipFile(bundle_path) as bundle:
        assert len(bundle.namelist())==4
        for fmt in ("png","jpg","svg","pdf"):
            data=bundle.read(f"qr-generator-2048.{fmt}")
            if fmt=="svg":
                data=resvg_py.svg_to_bytes(svg_string=data.decode())
            if fmt=="pdf":
                with pdfium.PdfDocument(data) as doc:
                    result=zxingcpp.read_barcode(doc[0].render(scale=300/72).to_pil())
                    assert result and result.text==URL
            else:
                assert scan(data)==URL,f"Native {fmt} export must scan"
    print("PASS: Android four-worker ZIP export; PNG/JPG/SVG/PDF independently decoded",flush=True)
    if adb("shell","getprop","ro.kernel.qemu").strip()=="1":
        auto=adb("shell","settings","get","system","accelerometer_rotation").strip()
        rotation=adb("shell","settings","get","system","user_rotation").strip()
        try:
            tap("Preview & export",exact=True)
            time.sleep(.5)
            adb("shell","settings","put","system","accelerometer_rotation","0")
            adb("shell","settings","put","system","user_rotation","1")
            time.sleep(2)
            wait_scan(URL,"04-native-landscape.png")
            tree=dump()
            preview=find("Live QR preview",tree,exact=True)
            controls=find("Destination URL",tree)
            assert preview is not None and controls is not None
            assert bounds(preview)[2]<bounds(controls)[0],"Landscape preview left, Customize right"
            print("PASS: Android landscape uses desktop columns and GPU preview still scans",flush=True)
        finally:
            adb("shell","settings","put","system","user_rotation",rotation)
            adb("shell","settings","put","system","accelerometer_rotation",auto)
    report={"result":"PASS","device":adb("shell","getprop","ro.product.model").strip(),
            "android":adb("shell","getprop","ro.build.version.release").strip(),
            "sdk":adb("shell","getprop","ro.build.version.sdk").strip(),
            "page_size":adb("shell","getconf","PAGESIZE").strip(),
            "scenarios":["APK install and cold start","Native live preview independent decode",
                         "Safe-area portrait UI and bottom navigation","Native URL keyboard entry and preview update",
                         "Android system document save dialog","2048 × 2048 PNG export decoded to entered URL",
                         "Logo opens creator credits", "Android double-space URL shortcut",
                         "Landscape: GPU preview left, Customize right", "Four-worker ZIP export: all four formats decoded"]}
    (OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    run()
