"""Real Flet UI -> upload -> export -> independent QR decode, desktop and portrait.

Run with QRSTUDIO_WEB=1 python src/main.py in a second terminal.
No renderer or file picker mocks are used.
"""
import io
import json
import os
import time
import zipfile
from pathlib import Path

import resvg_py
import pypdfium2 as pdfium
import zxingcpp
from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright
from e2e_logo import LOGO_URL, make_logo, assert_intact_logo, assert_qr_state

OUT=Path("test-results/e2e")
OUT.mkdir(parents=True,exist_ok=True)
URL="https://example.com/muphoto?event=e2e&photo=123"


def scan(data):
    image=Image.open(io.BytesIO(data)).convert("RGBA")
    base=Image.new("RGB",image.size,"white")
    base.paste(image,mask=image.getchannel("A"))
    result=zxingcpp.read_barcode(base)
    return result.text if result else None


def wait_ready(page):
    page.wait_for_timeout(400)
    expect(page.get_by_text("LIVE PREVIEW",exact=True)).to_be_visible(timeout=20000)
    expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_enabled()


def reveal(page,target):
    expect(target).to_be_visible(timeout=10000)
    for _ in range(24):
        box=target.bounding_box()
        if box is None:
            # Flutter can replace a semantics node between the visibility check
            # and its geometry query during the previous async UI update.
            page.wait_for_timeout(150)
            continue
        height=page.viewport_size["height"]
        center=box["y"]+box["height"]/2
        if 195<center<height-85:
            return
        x=max(40,min(page.viewport_size["width"]-40,box["x"]+box["width"]/2))
        page.mouse.move(x,height-170)
        page.mouse.wheel(0,max(-650,min(650,center-height/2)))
        page.wait_for_timeout(220)
    raise AssertionError(f"Could not scroll control into the actual viewport: {target}")


def tap(page,target):
    reveal(page,target)
    target.click(force=True)


def fill(page,label,value):
    target=page.get_by_label(label,exact=True)
    reveal(page,target)
    target.focus()
    # Flutter uses a separate focused text editor after the semantic node receives focus.
    editor=page.locator("input:focus, textarea:focus")
    expect(editor).to_be_attached(timeout=5000)
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(value)
    expect(editor).to_have_value(value)
    page.keyboard.press("Tab")


def select(page,label,value):
    tap(page,page.get_by_role("button",name=label,exact=True))
    page.get_by_role("button",name=value,exact=True).click(force=True)


def picker_hex(page,value):
    fill(page,"Hex color",value)
    rgb=value.lstrip("#")
    # Wait for server-side HSV/RGB synchronization, not only the browser's
    # immediate editable text. A fast click can otherwise hit the transient
    # disabled state while clearing/replacing the old value.
    for index,label in enumerate(("Red","Green","Blue")):
        page.get_by_label(label,exact=True).focus()
        expect(page.locator("input:focus, textarea:focus")).to_have_value(str(int(rgb[index*2:index*2+2],16)))
    expect(page.get_by_role("button",name="Apply color",exact=True)).to_be_enabled()


def set_slider(page,label,readout,fraction):
    heading=page.get_by_text(label,exact=True)
    reveal(page,heading)
    headingbox=heading.bounding_box()
    # Flutter bounds describe the thumb. Find the next thumb below this label,
    # then use the full row edges as the real pointer-input track.
    boxes=[s.bounding_box() for s in page.get_by_role("slider").all()]
    box=min((b for b in boxes if b and b["y"]>headingbox["y"]+headingbox["height"]/2),
            key=lambda b:b["y"])
    left=headingbox["x"]
    valuebox=page.get_by_text(readout,exact=True).bounding_box()
    right=valuebox["x"]+valuebox["width"]
    page.mouse.click(left+24+(right-left-48)*fraction,box["y"]+box["height"]/2)
    page.wait_for_timeout(300)


def save_download(page,label,path):
    with page.expect_download(timeout=90000) as event:
        tap(page,page.get_by_role("button",name=label,exact=True))
    event.value.save_as(path)
    return path.read_bytes()


def run():
    report={"scenarios":[],"console_errors":[],"target":os.environ.get("QRSTUDIO_TEST_TARGET","source")}
    logo=Image.new("RGBA",(400,180),"#FFFFFF")
    draw=ImageDraw.Draw(logo)
    draw.rounded_rectangle((10,10,390,170),radius=30,fill="#172033")
    draw.text((90,65),"M U P H O T O",fill="#D4F89A",font_size=30)
    logo_path=OUT/"wide-logo.png"
    logo.save(logo_path)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="msedge",headless=True)
        # Modern Android phones are high-DPI. Keep CSS viewport checks independent
        # from the physical screenshot resolution used by the QR decoder.
        context=browser.new_context(viewport={"width":1280,"height":900},accept_downloads=True,device_scale_factor=2)
        page=context.new_page()
        page.on("pageerror",lambda err:report["console_errors"].append(str(err)))
        page.goto(os.environ.get("QRSTUDIO_BASE_URL","http://127.0.0.1:8550"))
        page.locator("flt-semantics-placeholder").dispatch_event("click")
        wait_ready(page)
        page.wait_for_timeout(2000)
        page.screenshot(path=OUT/"01-desktop.png")
        assert scan((OUT/"01-desktop.png").read_bytes())=="https://example.com","GPU preview must independently scan"
        assert page.title()=="QR Generator"
        # Clear from the red suffix button, then collapse the invalid URL card.
        tap(page,page.get_by_role("button",name="Clear URL"))
        expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_disabled()
        tap(page,page.get_by_role("button",name="Collapse Where should it go?"))
        expect(page.get_by_label("Destination URL *",exact=True)).not_to_be_visible()
        expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_disabled()
        tap(page,page.get_by_role("button",name="Expand Where should it go?"))
        fill(page,"Destination URL *","https://example.com")
        wait_ready(page)
        for title,control in (("Find your shape",page.get_by_role("button",name="Body shape: Hexagon Hexagon",exact=True)),
                              ("Set the mood",page.get_by_label("Color",exact=True)),
                              ("Make it recognizably you",page.get_by_role("button",name="Choose logo",exact=True)),
                              ("Give it a background",page.get_by_label("Background color",exact=True))):
            tap(page,page.get_by_role("button",name="Collapse "+title))
            expect(control).not_to_be_visible()
            tap(page,page.get_by_role("button",name="Expand "+title))
            expect(control).to_be_visible()
        report["scenarios"].append("Red in-field Clear URL invalidates export; all five menus collapse to headers and expand without bypassing validation")
        assert page.get_by_role("button",name="Body shape: Rounded Rounded",exact=True).count()==0
        for kind in ("Body shape","Eye frame","Eye ball"):
            tap(page,page.get_by_role("button",name=f"{kind}: Octagon Octagon",exact=True))
        wait_ready(page)
        octagon=save_download(page,"Export QR code",OUT/"octagon.png")
        assert scan(octagon)=="https://example.com"
        page.mouse.move(260,400)
        page.mouse.wheel(0,-2200)
        page.wait_for_timeout(400)
        assert scan(page.screenshot(path=OUT/"octagon-preview.png"))=="https://example.com"
        for kind in ("Body shape","Eye frame","Eye ball"):
            tap(page,page.get_by_role("button",name=f"{kind}: Hexagon Hexagon",exact=True))
        wait_ready(page)
        hexagon=save_download(page,"Export QR code",OUT/"hexagon.png")
        assert scan(hexagon)=="https://example.com"
        page.mouse.move(260,400)
        page.mouse.wheel(0,-2200)
        page.wait_for_timeout(400)
        assert scan(page.screenshot(path=OUT/"hexagon-preview.png"))=="https://example.com"
        report["scenarios"].append("Rounded removed, Square Rounded retained; actual Octagon/Hexagon selection and decoded exports")
        before=save_download(page,"Export QR code",OUT/"before-advanced.png")
        select(page,"Ink color picker","Advanced")
        expect(page.get_by_text("Advanced ink color",exact=True)).to_be_visible()
        fill(page,"Hex color","invalid")
        expect(page.get_by_role("button",name="Apply color",exact=True)).to_be_disabled()
        page.get_by_role("button",name="Cancel",exact=True).click()
        after=save_download(page,"Export QR code",OUT/"after-cancel.png")
        assert before==after,"Cancel must not apply a draft or invalid color"
        tap(page,page.get_by_role("button",name="Pick ink color",exact=True))
        hue=page.get_by_role("button",name="Hue strip",exact=True).bounding_box()
        # Flutter's accessibility overlay turns pointer input into a centered
        # semantic tap. Route this gesture to the real Flutter canvas instead;
        # restore the overlay immediately for all other accessibility actions.
        pointer_style=page.add_style_tag(content="flt-semantics, flt-semantics-container { pointer-events: none !important; }")
        page.mouse.click(hue["x"]+hue["width"]/2,hue["y"]+hue["height"]*.5)
        square=page.get_by_role("button",name="Saturation and brightness",exact=True).bounding_box()
        page.mouse.move(square["x"]+square["width"]*.4,square["y"]+square["height"]*.4)
        page.mouse.down()
        page.mouse.move(square["x"]+square["width"]*.7,square["y"]+square["height"]*.65,steps=5)
        page.mouse.up()
        page.wait_for_timeout(400)
        pointer_style.evaluate("el => el.remove()")
        page.screenshot(path=OUT/"advanced-picker.png")
        page.mouse.move(square["x"]+80,square["y"]+square["height"]+70)
        page.mouse.wheel(0,240)
        page.wait_for_timeout(200)
        for label,expected in (("Hue °",180),("Sat. %",70),("Bright. %",35)):
            page.get_by_label(label,exact=True).focus()
            page.wait_for_timeout(120)
            value=page.locator("input:focus, textarea:focus").input_value()
            assert abs(float(value)-expected)<3,(label,value)
        page.get_by_label("Hex color",exact=True).focus()
        page.wait_for_timeout(120)
        draft=page.locator("input:focus, textarea:focus").input_value()
        page.set_viewport_size({"width":844,"height":450})
        page.wait_for_timeout(800)
        plane=page.get_by_role("button",name="Saturation and brightness",exact=True).bounding_box()
        assert plane and plane["height"]<=120 and 0<plane["y"]<plane["y"]+plane["height"]<450
        page.screenshot(path=OUT/"advanced-landscape.png")
        page.set_viewport_size({"width":1280,"height":900})
        page.wait_for_timeout(800)
        page.get_by_label("Hex color",exact=True).focus()
        page.wait_for_timeout(120)
        assert page.locator("input:focus, textarea:focus").input_value()==draft
        report["scenarios"].append("Advanced picker resizes in landscape with full color plane visible and draft preserved")
        fill(page,"Red","20")
        fill(page,"Green","40")
        fill(page,"Blue","60")
        page.get_by_label("Hex color",exact=True).focus()
        page.wait_for_timeout(120)
        assert page.locator("input:focus, textarea:focus").input_value()=="#14283C"
        fill(page,"Hue °","240")
        fill(page,"Sat. %","100")
        fill(page,"Bright. %","100")
        page.get_by_label("Hex color",exact=True).focus()
        page.wait_for_timeout(120)
        assert page.locator("input:focus, textarea:focus").input_value()=="#0000FF"
        picker_hex(page,"13243A")
        page.get_by_role("button",name="Apply color",exact=True).click()
        wait_ready(page)
        ink=save_download(page,"Export QR code",OUT/"advanced-ink.png")
        assert scan(ink)=="https://example.com"
        assert Image.open(io.BytesIO(ink)).convert("RGB").get_flattened_data().count((19,36,58))>1000
        report["scenarios"].append("Advanced ink picker: hue/SV pointer gestures, invalid HEX blocked, Cancel unchanged, Apply updates exported ink")
        select(page,"Background color picker","Advanced")
        expect(page.get_by_text("Advanced background color",exact=True)).to_be_visible()
        picker_hex(page,"F8F8F8")
        page.get_by_role("button",name="Apply color",exact=True).click()
        wait_ready(page)
        bg=save_download(page,"Export QR code",OUT/"advanced-bg.png")
        assert scan(bg)=="https://example.com"
        assert Image.open(io.BytesIO(bg)).convert("RGB").get_flattened_data().count((248,248,248))>1000
        report["scenarios"].append("Advanced background picker: exact HEX applies to actual exported background")
        select(page,"Ink style","Gradient")
        tap(page,page.get_by_role("button",name="Pick ink end color",exact=True))
        picker_hex(page,"513A80")
        page.get_by_role("button",name="Apply color",exact=True).click()
        wait_ready(page)
        assert scan(save_download(page,"Export QR code",OUT/"advanced-ink-gradient.png"))=="https://example.com"
        select(page,"Ink style","Plain")
        select(page,"Background style","Gradient")
        tap(page,page.get_by_role("button",name="Pick background end color",exact=True))
        picker_hex(page,"EAF2E5")
        page.get_by_role("button",name="Apply color",exact=True).click()
        wait_ready(page)
        assert scan(save_download(page,"Export QR code",OUT/"advanced-bg-gradient.png"))=="https://example.com"
        select(page,"Background style","Plain")
        report["scenarios"].append("Advanced pickers edit both gradient end colors while retaining Plain/Gradient controls")
        page.get_by_role("button",name="Credits",exact=True).click(force=True)
        expect(page.get_by_text("Jirawat Pratuangtip",exact=True)).to_be_visible()
        expect(page.get_by_text("github.com/Jirawat2105",exact=True)).to_be_visible()
        page.get_by_role("button",name="Close",exact=True).click(force=True)
        report["scenarios"].append("QR Generator branding, logo opens Credits with creator and GitHub on separate lines")
        fill(page,"Destination URL *","example.org/tab-shortcut")
        wait_ready(page)
        shortcut=save_download(page,"Export QR code",OUT/"tab-shortcut.png")
        assert scan(shortcut)=="https://example.org/tab-shortcut"
        report["scenarios"].append("Windows Tab completes the correct https:// prefix; Android double-space is tested natively")
        fill(page,"Destination URL *",URL)
        wait_ready(page)
        fill(page,"Export resolution (px)","1024")
        wait_ready(page)
        initial=save_download(page,"Export QR code",OUT/"01-plain.png")
        assert scan(initial)==URL,"UI-entered URL must be decoded from downloaded PNG"
        print("PASS: URL entry, resolution and actual PNG download/decode",flush=True)
        report["scenarios"].append("Desktop URL entry, custom resolution and PNG export decoded")

        fill(page,"Destination URL *","")
        expect(page.get_by_text("Enter a complete URL",exact=False)).to_be_visible()
        expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_disabled()
        fill(page,"Destination URL *",URL)
        wait_ready(page)
        fill(page,"Export resolution (px)","bad")
        expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_disabled()
        tap(page,page.get_by_role("switch",name="Minimalist QR",exact=True))
        expect(page.get_by_role("button",name="Export QR code",exact=True)).to_be_disabled()
        fill(page,"Export resolution (px)","1024")
        wait_ready(page)
        tap(page,page.get_by_role("switch",name="Minimalist QR",exact=True))
        wait_ready(page)
        report["scenarios"].append("Required URL and invalid resolution block exports across subsequent changes")

        tap(page,page.get_by_role("button",name="Body shape: Dots Dots",exact=True))
        tap(page,page.get_by_role("button",name="Eye frame: Circle Circle",exact=True))
        tap(page,page.get_by_role("button",name="Eye ball: Circle Circle",exact=True))
        select(page,"Ink style","Gradient")
        wait_ready(page)
        fill(page,"Color","#172033")
        fill(page,"End color","#7957D5")
        wait_ready(page)
        report["scenarios"].append("Body and finder shapes, gradient ink and custom hex colors")

        tap(page,page.get_by_role("switch",name="Minimalist QR",exact=True))
        tap(page,page.get_by_role("button",name="Body shape: Diamond Diamond",exact=True))
        tap(page,page.get_by_role("button",name="Eye frame: Leaf Leaf",exact=True))
        tap(page,page.get_by_role("button",name="Eye ball: Diamond Diamond",exact=True))
        wait_ready(page)
        styled=save_download(page,"Export QR code",OUT/"minimalist-diamonds.png")
        assert scan(styled)==URL
        tap(page,page.get_by_role("switch",name="Minimalist QR",exact=True))
        wait_ready(page)
        styled=save_download(page,"Export QR code",OUT/"diamond-leaf-regression.png")
        assert scan(styled)==URL
        report["scenarios"].append("Minimalist keeps shapes/colors editable; reported diamond/leaf combination exports and scans")

        with page.expect_file_chooser() as event:
            tap(page,page.get_by_role("button",name="Choose logo",exact=True))
        event.value.set_files(logo_path)
        expect(page.get_by_text("wide-logo.png · original aspect ratio",exact=True)).to_be_visible()
        wait_ready(page)
        select(page,"Scale relative to QR","Height")
        wait_ready(page)
        expect(page.get_by_text("Logo auto-fitted",exact=False)).to_be_visible()
        select(page,"Scale relative to QR","Width")
        wait_ready(page)
        tap(page,page.get_by_role("switch",name="Reserve space for logo",exact=True))
        wait_ready(page)
        tap(page,page.get_by_role("switch",name="Reserve space for logo",exact=True))
        wait_ready(page)
        report["scenarios"].append("Actual image upload, original aspect ratio, width/height selection and reservation toggle")

        select(page,"Background style","Gradient")
        wait_ready(page)
        select(page,"Background style","Plain")
        wait_ready(page)
        # Test image background selection with an actual upload, then return to a scannable light background.
        select(page,"Background style","Image")
        with page.expect_file_chooser() as event:
            tap(page,page.get_by_role("button",name="Choose background",exact=True))
        event.value.set_files(logo_path)
        wait_ready(page)
        select(page,"Background style","Plain")
        wait_ready(page)
        report["scenarios"].append("Solid/gradient/photo backgrounds and actual background upload")

        bundle=save_download(page,"Export all formats (.zip)",OUT/"qr-all.zip")
        with zipfile.ZipFile(io.BytesIO(bundle)) as z:
            assert len(z.namelist())==4
            for ext in ("png","jpg","svg","pdf"):
                data=z.read(f"qr-generator-1024.{ext}")
                (OUT/f"styled.{ext}").write_bytes(data)
                if ext=="svg":
                    assert 'preserveAspectRatio="xMidYMid meet"' in data.decode()
                    data=resvg_py.svg_to_bytes(svg_string=data.decode())
                if ext=="pdf":
                    assert data.startswith(b"%PDF-")
                    with pdfium.PdfDocument(data) as document:
                        qr=zxingcpp.read_barcode(document[0].render(scale=300/72).to_pil())
                        assert qr and qr.text==URL,"Exported PDF must independently decode"
                else:
                    assert scan(data)==URL,f"Styled {ext} from actual UI must scan"
        report["scenarios"].append("Multicore all-format ZIP contains PNG/JPG/SVG/PDF; independent decode of raster and SVG")

        select(page,"File format","SVG")
        svg=save_download(page,"Export QR code",OUT/"single.svg")
        assert scan(resvg_py.svg_to_bytes(svg_string=svg.decode()))==URL
        report["scenarios"].append("Individual format selection and SVG download")
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT/"02-mobile.png")
        assert scan((OUT/"02-mobile.png").read_bytes())==URL,"Styled GPU preview with logo must scan"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        # The portrait app has one vertical scroll area, with the live preview first.
        expect(page.get_by_text("Your QR, live.",exact=True)).to_be_visible()
        page.get_by_role("button",name="Customize",exact=True).click(force=True)
        page.wait_for_timeout(800)
        box=page.get_by_label("Destination URL *",exact=True).bounding_box()
        assert box and 150<box["y"]<760,"Mobile Customize button must reveal URL controls"
        heading=page.get_by_text("Small code. Big possibilities.",exact=True)
        box=heading.bounding_box() if heading.count() else None
        assert box is None or box["y"]<80,"Android-style portrait heading must scroll with content"
        page.get_by_role("button",name="Preview & export",exact=True).click(force=True)
        page.wait_for_timeout(800)
        expect(page.get_by_text("Your QR, live.",exact=True)).to_be_visible()
        report["scenarios"].append("390 × 844 portrait layout, live preview visible, no horizontal overflow")
        page.set_viewport_size({"width":844,"height":450})
        page.wait_for_timeout(1600)
        qrbox=page.get_by_role("img",name="Live QR preview",exact=True).bounding_box()
        urlbox=page.get_by_label("Destination URL *",exact=True).bounding_box()
        assert qrbox and urlbox and qrbox["x"]+qrbox["width"]<urlbox["x"],"Landscape preview must be left, settings right"
        page.screenshot(path=OUT/"03-landscape.png")
        report["scenarios"].append("844 × 450 landscape uses desktop columns: GPU preview left, Customize right")
        # Reproduce the actual Android report: version 8 has an alignment eye
        # exactly at the logo center. Check artwork pixels as well as decoding.
        page.set_viewport_size({"width":1280,"height":900})
        page.wait_for_timeout(800)
        fill(page,"Destination URL *",LOGO_URL)
        for label in ("Body shape: Square Rounded Square Rounded", "Eye frame: Square Rounded Square Rounded", "Eye ball: Square Rounded Square Rounded"):
            tap(page,page.get_by_role("button",name=label,exact=True))
        select(page,"Ink style","Plain")
        square_logo=OUT/"QR-logo-regression.png"
        make_logo(square_logo)
        with page.expect_file_chooser() as chooser:
            tap(page,page.get_by_role("button",name="Choose logo",exact=True))
        chooser.value.set_files(square_logo)
        fill(page,"Export resolution (px)","4000")
        wait_ready(page)
        data=save_download(page,"Export all formats (.zip)",OUT/"logo49-all.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            for ext in ("png","jpg","svg","pdf"):
                exported=bundle.read(f"qr-generator-4000.{ext}")
                if ext=="svg":
                    exported=resvg_py.svg_to_bytes(svg_string=exported.decode())
                if ext=="pdf":
                    with pdfium.PdfDocument(exported) as document:
                        buffer=io.BytesIO()
                        document[0].render(scale=300/72).to_pil().save(buffer,"PNG")
                        exported=buffer.getvalue()
                assert scan(exported)==LOGO_URL
                assert_intact_logo(exported)
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_timeout(1000)
        page.get_by_role("button",name="Preview & export",exact=True).click(force=True)
        page.wait_for_timeout(900)
        preview=page.screenshot(path=OUT/"04-logo49-portrait.png")
        assert scan(preview)==LOGO_URL
        assert_intact_logo(preview)
        report["scenarios"].append("49x49 logo regression: intact GPU artwork and 4000px PNG/JPG/SVG/PDF; all independently decoded")
        page.set_viewport_size({"width":1280,"height":900})
        page.wait_for_timeout(800)
        wide=OUT/"wordmark-logo.png"
        make_logo(wide, (1200,280))
        with page.expect_file_chooser() as chooser:
            tap(page,page.get_by_role("button",name="Choose logo",exact=True))
        chooser.value.set_files(wide)
        tap(page,page.get_by_role("switch",name="Wide wordmark",exact=True))
        for fraction, label, readout in ((.87,"Logo size · % of QR area","20%"),
                                         (.2,"Space around logo","1 modules")):
            set_slider(page,label,readout,fraction)
        page.screenshot(path=OUT/"05-wordmark-settings.png")
        select(page,"File format","PNG")
        wait_ready(page)
        wordmark=save_download(page,"Export QR code",OUT/"square-rounded-wordmark.png")
        assert scan(wordmark)==LOGO_URL
        x1,y1,x2,y2=assert_intact_logo(wordmark)
        assert x2-x1>2000,"Wide wordmark setting must actually exceed the compact 25% cap"
        assert abs((x2-x1)/(y2-y1)-1200/280)<.04,"Wordmark ratio must stay original"
        report["scenarios"].append("Square Rounded reference style and Wide wordmark: real slider adjustments, proportional logo >50% of output width, exported PNG decoded")
        # Minimalist must stay enabled through actual artwork removal/import.
        # A long URL exposes the previous silent fallback: H 49 vs Q 41.
        tap(page,page.get_by_role("button",name="Remove logo"))
        tap(page,page.get_by_role("switch",name="Wide wordmark",exact=True))
        set_slider(page,"Logo size · % of QR area","70%",.2)
        tap(page,page.get_by_role("switch",name="Minimalist QR",exact=True))
        wait_ready(page)
        expect(page.get_by_text("Minimalist · 37 × 37 modules",exact=False)).to_be_visible()
        with page.expect_file_chooser() as chooser:
            tap(page,page.get_by_role("button",name="Choose logo",exact=True))
        chooser.value.set_files(square_logo)
        wait_ready(page)
        expect(page.get_by_role("switch",name="Minimalist QR",exact=True)).to_be_checked()
        expect(page.get_by_text("Minimalist · 41 × 41 modules",exact=False)).to_be_visible()
        expect(page.get_by_text("Regular: 49 × 49",exact=False)).to_be_visible()
        minimal_bundle=save_download(page,"Export all formats (.zip)",OUT/"minimal-logo-all.zip")
        with zipfile.ZipFile(io.BytesIO(minimal_bundle)) as bundle:
            for ext in ("png","jpg","svg","pdf"):
                data=bundle.read(f"qr-generator-4000.{ext}")
                if ext=="svg": data=resvg_py.svg_to_bytes(svg_string=data.decode())
                if ext=="pdf":
                    with pdfium.PdfDocument(data) as document:
                        buffer=io.BytesIO()
                        document[0].render(scale=300/72).to_pil().save(buffer,"PNG")
                        data=buffer.getvalue()
                assert scan(data)==LOGO_URL
                assert_qr_state(data,LOGO_URL,"Q",41)
                assert_intact_logo(data)
        report["scenarios"].append("Minimalist remains enabled on real logo import: 49-to-41 modules, intact logo and all four exports independently decoded")
        # Toggle rapidly, ending ON, so a late Regular render cannot win.
        switch=page.get_by_role("switch",name="Minimalist QR",exact=True)
        reveal(page,switch)
        for _ in range(4): switch.click(force=True)
        wait_ready(page)
        expect(switch).to_be_checked()
        expect(page.get_by_text("Minimalist · 41 × 41 modules",exact=False)).to_be_visible()
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_timeout(800)
        page.get_by_role("button",name="Preview & export",exact=True).click(force=True)
        page.wait_for_timeout(800)
        compact_preview=page.screenshot(path=OUT/"06-minimal-logo.png")
        assert_qr_state(compact_preview,LOGO_URL,"Q",41)
        assert_intact_logo(compact_preview)
        page.set_viewport_size({"width":1280,"height":900})
        page.wait_for_timeout(800)
        tap(page,page.get_by_role("button",name="Remove logo"))
        wait_ready(page)
        expect(page.get_by_text("Minimalist · 37 × 37 modules",exact=False)).to_be_visible()
        tap(page,switch)
        wait_ready(page)
        expect(page.get_by_text("Regular · 49 × 49 modules",exact=False)).to_be_visible()
        report["scenarios"].append("Rapid Minimalist toggles and logo removal preserve latest mode; OFF restores Regular 49x49")
        browser.close()
    assert not report["console_errors"],report["console_errors"]
    report["result"]="PASS"
    (OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    run()
