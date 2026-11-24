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
import tomllib
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import zxingcpp
import resvg_py
import pypdfium2 as pdfium
from PIL import Image
from e2e_logo import LOGO_URL, make_logo, assert_intact_logo, assert_qr_state

ADB=shutil.which("adb")
PACKAGE="com.muphoto.muphoto_qr_studio"
OUT=Path("test-results/android")
OUT.mkdir(parents=True,exist_ok=True)
URL=LOGO_URL
RUN_ID=str(time.time_ns())


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


def select_shape(section, shape):
    # Android exposes the tile label alone; the web semantics also include its
    # tooltip. Scope identical shape labels using the visible section heading.
    scroll_to(section)
    width,height=map(int,re.findall(r"\d+",adb("shell","wm","size"))[-2:])
    for _ in range(6):
        tree=dump()
        heading=find(section,tree,exact=True)
        assert heading is not None,f"Shape section must remain visible: {section}"
        bottom=bounds(heading)[3]
        candidates=[node for node in tree.iter("node")
                    if node.get("content-desc")==shape and bottom<bounds(node)[1]
                    and bounds(node)[3]<height*.84]
        if candidates:
            tap_node(min(candidates,key=lambda node:bounds(node)[1]))
            return
        adb("shell","input","swipe",str(width//2),str(int(height*.72)),str(width//2),str(int(height*.57)),"650")
    raise AssertionError(f"Could not select {shape} in {section}")


def set_switch(label, enabled):
    scroll_to(label)
    tree=dump()
    switches=[node for node in tree.iter("node") if node.get("checkable")=="true"
              and label in (node.get("content-desc","")+node.get("text",""))]
    assert len(switches)==1,f"Expected one native switch: {label}"
    if (switches[0].get("checked")=="true") != enabled:
        tap_node(switches[0])
    time.sleep(.5)


def save_document(filename, local_name):
    """Use a unique system-picker filename, then pull exactly this run's file.

    Reusing a list of Downloads names could accidentally validate an older
    successful export and hide a regression in the newly installed APK.
    """
    time.sleep(1)
    tree=dump()
    fields=[node for node in tree.iter("node") if node.get("class")=="android.widget.EditText"
            and node.get("enabled")=="true"]
    assert len(fields)==1,"Android Save dialog must expose its filename field"
    node=fields[0]
    tap_node(node)
    adb("shell","input","keyevent","123")
    if node.get("text"):
        adb("shell","input","keyevent",*(["67"]*len(node.get("text"))))
    adb("shell","input","text",filename)
    save=find("SAVE",exact=True)
    if save is None: save=find("Save",exact=True)
    assert save is not None,"Native document Save button must be visible"
    tap_node(save)
    remote="/sdcard/Download/"+filename
    for _ in range(25):
        try:
            adb("shell","test","-s",remote)
            break
        except RuntimeError:
            time.sleep(.4)
    else:
        raise AssertionError(f"This run's export was not written: {filename}")
    path=OUT/local_name
    adb("pull",remote,str(path))
    return path.read_bytes()


def check_bundle(data,ecc,modules):
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        assert len(bundle.namelist())==4
        for fmt in ("png","jpg","svg","pdf"):
            item=bundle.read(f"qr-generator-2048.{fmt}")
            if fmt=="svg": item=resvg_py.svg_to_bytes(svg_string=item.decode())
            if fmt=="pdf":
                with pdfium.PdfDocument(item) as document:
                    buffer=io.BytesIO()
                    document[0].render(scale=300/72).to_pil().save(buffer,"PNG")
                    item=buffer.getvalue()
            assert_qr_state(item,URL,ecc,modules)
            assert_intact_logo(item)


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
    expected_version=tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert "versionName="+expected_version in adb("shell","dumpsys","package",PACKAGE),"Installed APK must match this source version"
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
    adb("shell","input","text",URL.removeprefix("https://")+"%s%s")
    time.sleep(.8)
    edited=find("Destination URL")
    assert edited is not None and edited.get("text")==URL,"Android double-space must add https:// before blur"
    adb("shell","input","keyevent","4") # close keyboard
    time.sleep(.8)
    tap("Customize",exact=True)
    time.sleep(.8)
    for label in ("Body shape", "Eye frame", "Eye ball"):
        select_shape(label,"Square Rounded")
        time.sleep(.3)
    # Import a real opaque image through Android's document provider. Its
    # central green pixels must survive both the GPU preview and all exports.
    logo_path=OUT/"QR-logo-regression.png"
    make_logo(logo_path)
    adb("push",str(logo_path),"/sdcard/Download/QR-logo-regression.png")
    adb("shell","am","broadcast","-a","android.intent.action.MEDIA_SCANNER_SCAN_FILE",
        "-d","file:///sdcard/Download/QR-logo-regression.png")
    tap_node(scroll_to("Choose logo"))
    time.sleep(2)
    selected=find("QR-logo-regression.png")
    if selected is None:
        tap("Show roots",exact=True)
        time.sleep(.5)
        tap("Downloads",exact=True)
        time.sleep(1)
        selected=find("QR-logo-regression.png")
    assert selected is not None,"Uploaded test logo must be available in Android Files"
    tap_node(selected)
    time.sleep(1.5)
    print("PASS: real Android document picker imported the logo",flush=True)
    tap("Preview & export",exact=True)
    time.sleep(.8)
    wait_scan(URL,"02-updated-preview.png")
    assert_intact_logo((OUT/"02-updated-preview.png").read_bytes())
    print("PASS: native URL entry and preview update decoded",flush=True)
    # Every export is saved under a unique, observed system-dialog filename.
    tap_node(scroll_to("Export QR code"))
    png=save_document(f"qr-e2e-{RUN_ID}-regular.png","native-export.png")
    assert Image.open(io.BytesIO(png)).size==(2048,2048)
    assert_qr_state(png,URL,"H",49)
    assert_intact_logo(png)
    screenshot("03-native-export.png")
    print("PASS: native Save dialog; fresh PNG decoded as H/49",flush=True)
    tap_node(scroll_to("Export all formats (.zip)"))
    regular_bundle=save_document(f"qr-e2e-{RUN_ID}-regular.zip","native-all.zip")
    check_bundle(regular_bundle,"H",49)
    print("PASS: fresh Regular PNG/JPG/SVG/PDF decoded as H/49",flush=True)
    tap("Customize",exact=True)
    time.sleep(.8)
    set_switch("Minimalist QR",True)
    tap("Preview & export",exact=True)
    time.sleep(.8)
    wait_scan(URL,"05-native-minimal-logo.png")
    assert_qr_state((OUT/"05-native-minimal-logo.png").read_bytes(),URL,"Q",41)
    assert_intact_logo((OUT/"05-native-minimal-logo.png").read_bytes())
    tap_node(scroll_to("Export all formats (.zip)"))
    minimal_bundle=save_document(f"qr-e2e-{RUN_ID}-minimal.zip","native-minimal-all.zip")
    check_bundle(minimal_bundle,"Q",41)
    print("PASS: Minimalist logo preview + all four fresh exports decoded as Q/41",flush=True)
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
            assert_intact_logo((OUT/"04-native-landscape.png").read_bytes())
            assert_qr_state((OUT/"04-native-landscape.png").read_bytes(),URL,"Q",41)
            tree=dump()
            preview=find("Live QR preview",tree,exact=True)
            controls=find("Destination URL",tree)
            assert preview is not None and controls is not None
            assert bounds(preview)[2]<bounds(controls)[0],"Landscape preview left, Customize right"
            print("PASS: Android landscape uses desktop columns and GPU preview still scans",flush=True)
        finally:
            adb("shell","settings","put","system","user_rotation",rotation)
            adb("shell","settings","put","system","accelerometer_rotation",auto)
    tap("Customize",exact=True)
    time.sleep(.8)
    tap_node(scroll_to("Remove logo"))
    tap("Preview & export",exact=True)
    time.sleep(.8)
    wait_scan(URL,"06-native-minimal-no-logo.png")
    assert_qr_state((OUT/"06-native-minimal-no-logo.png").read_bytes(),URL,"M",37)
    tap("Customize",exact=True)
    time.sleep(.8)
    set_switch("Minimalist QR",False)
    tap("Preview & export",exact=True)
    time.sleep(.8)
    wait_scan(URL,"07-native-regular-restored.png")
    assert_qr_state((OUT/"07-native-regular-restored.png").read_bytes(),URL,"H",49)
    print("PASS: removing logo retains Minimalist M/37; OFF restores H/49",flush=True)
    report={"result":"PASS","device":adb("shell","getprop","ro.product.model").strip(),
            "android":adb("shell","getprop","ro.build.version.release").strip(),
            "sdk":adb("shell","getprop","ro.build.version.sdk").strip(),
            "page_size":adb("shell","getconf","PAGESIZE").strip(),
            "scenarios":["APK install and cold start","Native live preview independent decode",
                         "Safe-area portrait UI and bottom navigation","Native URL keyboard entry and preview update",
                         "Android system document save dialog","2048 × 2048 PNG export decoded to entered URL",
                         "Logo opens creator credits", "Android double-space URL shortcut",
                         "Landscape: GPU preview left, Customize right", "Four-worker ZIP export: all four formats decoded",
                         "Real Android document picker logo import", "49x49 QR: intact logo pixels in portrait/landscape GPU preview and all four exports",
                         "Square Rounded body, eye frame and eye ball selected natively",
                         "Minimalist with logo: actual Q/41 preview and all four exports",
                         "Logo removal keeps Minimalist M/37; OFF restores Regular H/49",
                         "Unique system Save filenames prevent stale Downloads from passing"]}
    (OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    run()
