import io
import re
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest
import resvg_py
import pypdfium2 as pdfium
import zxingcpp
from PIL import Image, ImageDraw

from qrstudio.engine import (BODY_SHAPES, FRAME_SHAPES, BALL_SHAPES, Design,
                             load_image, logo_geometry, png_bytes, qr_matrix, render)


def decode(data):
    image=Image.open(io.BytesIO(data)).convert("RGBA")
    white=Image.new("RGB",image.size,"white")
    white.paste(image,mask=image.getchannel("A"))
    result=zxingcpp.read_barcode(white)
    return result.text if result else None


@pytest.fixture
def logo():
    img=Image.new("RGBA",(400,160),"#D4F89A")
    draw=ImageDraw.Draw(img)
    draw.rectangle((10,10,80,150),fill="#172033")
    draw.ellipse((260,10,390,150),fill="#172033")
    return png_bytes(img)


@pytest.mark.parametrize("field,values",[("body",BODY_SHAPES),("eye_frame",FRAME_SHAPES),("eye_ball",BALL_SHAPES)])
def test_shapes_scan(field,values):
    for value in values:
        d=replace(Design(resolution=768),**{field:value})
        data,_=render(d)
        assert decode(data)==d.url,(field,value)


@pytest.mark.parametrize("fmt",["PNG","SVG","JPG","PDF"])
def test_export_formats(fmt,tmp_path):
    d=Design(url="https://example.com/gallery?event=123&photo=456",resolution=1024,color_mode="Gradient")
    data,meta=render(d,fmt)
    (tmp_path/f"qr.{fmt.lower()}").write_bytes(data)
    assert meta["width"]==1024
    if fmt=="SVG":
        root=ET.fromstring(data)
        assert root.attrib["viewBox"]
        assert "<rect" in data.decode()
        data=resvg_py.svg_to_bytes(svg_string=data.decode())
    if fmt=="PDF":
        assert data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")
        with pdfium.PdfDocument(data) as document:
            image=document[0].render(scale=300/72).to_pil()
            qr=zxingcpp.read_barcode(image)
            assert qr and qr.text==d.url
    else:
        assert decode(data)==d.url
        assert Image.open(io.BytesIO(data)).size==(1024,1024)


@pytest.mark.parametrize("axis,scale",[("Width",22),("Height",8)])
def test_original_logo_aspect_and_scan(logo,axis,scale):
    d=Design(logo=logo,logo_axis=axis,logo_scale=scale,resolution=1200)
    n=len(qr_matrix(d.url)[0])
    x,y,w,h=logo_geometry(d,n)
    assert w/h==pytest.approx(2.5)
    assert (w if axis=="Width" else h)==pytest.approx(n*scale/100)
    data,_=render(d)
    assert decode(data)==d.url
    svg,_=render(d,"SVG")
    assert 'preserveAspectRatio="xMidYMid meet"' in svg.decode()
    assert decode(resvg_py.svg_to_bytes(svg_string=svg.decode()))==d.url


def test_reservation_toggle_changes_data_but_not_logo_aspect(logo):
    d=Design(logo=logo,resolution=768,logo_padding=1)
    a,_=render(d)
    b,_=render(replace(d,reserve_logo=False))
    assert a!=b
    assert decode(a)==d.url
    assert decode(b)==d.url


def test_transparent_and_soft_background():
    d=Design(resolution=768,background_opacity=40,background_rounding=20,edge_blur=10,edge_opacity=0)
    data,_=render(d)
    img=Image.open(io.BytesIO(data))
    assert img.mode=="RGBA"
    assert img.getpixel((0,0))[3]==0
    assert 0<img.getpixel((384,40))[3]<=102
    assert img.getextrema()[3][1]==255  # ink remains fully opaque
    assert decode(data)==d.url
    jpg,_=render(d,"JPG")
    assert Image.open(io.BytesIO(jpg)).mode=="RGB"


def test_gradient_and_photo_background(logo):
    for mode in ("Gradient","Image"):
        d=Design(resolution=768,background_mode=mode,background_end="#EAE2FA",background_image=logo)
        data,meta=render(d)
        assert Image.open(io.BytesIO(data)).size==(768,768)
        if mode=="Image":
            assert meta["warnings"]
        else:
            assert decode(data)==d.url


def test_minimalist_keeps_customization():
    d=Design(resolution=768,minimalist=True,body="Dots",eye_frame="Circle",eye_ball="Diamond",color_mode="Gradient")
    a,_=render(d)
    b,_=render(replace(d,body="Square",eye_frame="Square",eye_ball="Square",color_mode="Plain"))
    assert a!=b
    assert decode(a)==d.url
    _,meta=render(d)
    assert meta["ecc"].startswith("M")


@pytest.mark.parametrize("url", ["https://example.com", "https://example.com/abc", "https://example.com/"+"a"*50])
@pytest.mark.parametrize("with_logo", [False, True])
def test_minimalist_toggle_is_not_overridden_by_logo(url, with_logo):
    logo=png_bytes(Image.new("RGBA",(300,300),"#19C47D")) if with_logo else None
    d=Design(url=url,logo=logo,body="Square Rounded",resolution=1024)
    regular,normal=render(d)
    minimal,small=render(replace(d,minimalist=True))
    assert small["mode"]=="Minimalist"
    assert small["ecc"].startswith("Q" if with_logo else "M")
    assert small["modules"]<=normal["modules"]
    assert regular!=minimal  # Even equal-size grids must encode the chosen ECC.
    assert small["regular_modules"]==normal["modules"]
    assert minimal!=regular  # Even when both fit the same grid, ECC/matrix changes.
    if url.endswith("a"*50):
        assert (normal["modules"],small["modules"])==(49,41 if with_logo else 37)
    assert decode(minimal)==decode(regular)==url
    restored,meta=render(replace(d,minimalist=False))
    assert restored==regular and meta["mode"]=="Regular"


@pytest.mark.parametrize("fmt", ["PNG","JPG","SVG","PDF"])
@pytest.mark.parametrize("axis", ["Width","Height"])
@pytest.mark.parametrize("reserve", [True,False])
def test_minimalist_logo_exports_match_preview_and_scan(fmt,axis,reserve):
    logo=png_bytes(Image.new("RGBA",(400,180),"#19C47D"))
    d=Design(url="https://example.com/"+"a"*50,minimalist=True,logo=logo,
             logo_axis=axis,logo_scale=10, reserve_logo=reserve, body="Square Rounded",
             eye_frame="Square Rounded",eye_ball="Square Rounded",color_mode="Gradient",resolution=1024)
    _,preview=render(d,"PREVIEW",640)
    data,export=render(d,fmt)
    assert (export["mode"],export["modules"],export["ecc"])==(preview["mode"],preview["modules"],preview["ecc"])
    assert export["modules"]==41 and export["ecc"].startswith("Q")
    assert logo_geometry(d,41)[2]/logo_geometry(d,41)[3]==pytest.approx(400/180)
    if fmt=="SVG":
        data=resvg_py.svg_to_bytes(svg_string=data.decode())
    if fmt=="PDF":
        with pdfium.PdfDocument(data) as document:
            qr=zxingcpp.read_barcode(document[0].render(scale=300/72).to_pil())
    else:
        qr=zxingcpp.read_barcode(Image.open(io.BytesIO(data)))
    assert qr and qr.text==d.url
    assert qr.ec_level=="Q" and int(qr.extra["Version"])*4+17==41


def test_minimalist_add_remove_logo_does_not_reset_mode():
    d=Design(url="https://example.com/"+"a"*50,minimalist=True,resolution=768)
    before,first=render(d)
    with_logo=replace(d,logo=png_bytes(Image.new("RGBA",(300,300),"#19C47D")))
    imported,second=render(with_logo)
    removed,last=render(replace(with_logo,logo=None))
    assert [first["modules"],second["modules"],last["modules"]]==[37,41,37]
    assert first["mode"]==second["mode"]==last["mode"]=="Minimalist"
    assert before==removed
    assert decode(imported)==d.url


@pytest.mark.parametrize("field,value",[(field,value) for field,values in
    (("body",BODY_SHAPES),("eye_frame",FRAME_SHAPES),("eye_ball",BALL_SHAPES)) for value in values])
def test_each_shape_scans_in_minimalist_with_default_logo(field,value):
    d=replace(Design(minimalist=True,logo=png_bytes(Image.new("RGBA",(300,300),"#19C47D")),
                     resolution=1024),**{field:value})
    data,meta=render(d)
    assert meta["mode"]=="Minimalist" and meta["ecc"].startswith("Q")
    assert decode(data)==d.url,(field,value)


@pytest.mark.parametrize("shape",["Octagon","Hexagon"])
@pytest.mark.parametrize("field",["body","eye_frame","eye_ball"])
@pytest.mark.parametrize("fmt",["PNG","SVG","JPG","PDF"])
def test_polygon_shapes_export_and_scan(shape,field,fmt):
    d=replace(Design(url="https://example.com/"+"a"*50,resolution=1024,minimalist=True),**{field:shape})
    data,_=render(d,fmt)
    if fmt=="SVG": data=resvg_py.svg_to_bytes(svg_string=data.decode())
    if fmt=="PDF":
        with pdfium.PdfDocument(data) as document:
            qr=zxingcpp.read_barcode(document[0].render(scale=300/72).to_pil())
    else: qr=zxingcpp.read_barcode(Image.open(io.BytesIO(data)))
    assert qr and qr.text==d.url


@pytest.mark.parametrize("hex_value,rgb,hue",[("#FF0000",(255,0,0),0),("00FF00",(0,255,0),120),
    ("#0000ff",(0,0,255),240),("#FE6703",(254,103,3),23.9),("#FFFFFF",(255,255,255),0),
    ("#000000",(0,0,0),0)])
def test_advanced_color_rgb_hsv_roundtrip(hex_value,rgb,hue):
    from qrstudio.colors import ColorState
    state=ColorState.from_hex(hex_value)
    assert state.rgb==rgb
    assert state.hue==pytest.approx(hue,abs=.1)
    assert ColorState.from_rgb(*state.rgb).hex=="#"+hex_value.lstrip("#").upper()


@pytest.mark.parametrize("value",["","#FFF","#GGFF00","#FF000000","12345","#12 345"])
def test_advanced_color_rejects_invalid_hex(value):
    from qrstudio.colors import ColorState
    with pytest.raises(ValueError): ColorState.from_hex(value)


@pytest.mark.parametrize("url",["","hello","ftp://example.com","https://","https://a b.com","https://[bad","https://example.com:bad"])
def test_url_required(url):
    with pytest.raises(ValueError):
        render(Design(url=url))


@pytest.mark.parametrize("options",[{"resolution":0},{"resolution":8193},{"resolution":True},{"color":"red"},{"logo_scale":81},{"body":"wrong"},{"background_opacity":101}])
def test_invalid_settings(options):
    with pytest.raises(ValueError):
        render(replace(Design(),**options))


def test_oversized_logo_is_proportionally_auto_fitted(logo):
    d=Design(logo=logo,logo_axis="Height",logo_scale=40,resolution=768)
    n=len(qr_matrix(d.url)[0])
    _,_,w,h=logo_geometry(d,n)
    assert w/h==pytest.approx(2.5)
    assert max(w,h)<=n*.25+1e-9
    assert max(w,h)<=n-16+1e-9
    data,meta=render(d)
    assert decode(data)==d.url
    assert any("auto-fitted" in w for w in meta["warnings"])


def test_diamond_functional_cells_do_not_turn_into_squares():
    d=Design(body="Diamond",eye_frame="Leaf",eye_ball="Diamond",resolution=1024)
    packet,_=render(d,"PREVIEW",640)
    assert all(kind!="Square" for kind,*_ in packet["ops"])
    png,_=render(d)
    assert decode(png)==d.url
    svg,_=render(d,"SVG")
    assert decode(resvg_py.svg_to_bytes(svg_string=svg.decode()))==d.url


def test_leaf_diamond_gradient_logo_round_trip(logo):
    d=Design(url="https://example.com/muphoto?event=e2e&photo=123",body="Diamond",eye_frame="Leaf",
             eye_ball="Diamond",color_mode="Gradient",logo=logo,resolution=1024)
    for fmt in ("PNG","SVG"):
        data,_=render(d,fmt)
        if fmt=="SVG":
            data=resvg_py.svg_to_bytes(svg_string=data.decode())
        assert decode(data)==d.url


@pytest.mark.parametrize("reserve", [False, True])
@pytest.mark.parametrize("fmt", ["PNG", "JPG", "SVG", "PDF", "PREVIEW"])
def test_version8_logo_is_intact_and_exports_scan(reserve, fmt):
    # The reported Android screenshot is 49 x 49. Earlier short-URL tests had
    # no central alignment marker and could not detect holes in the artwork.
    url = "https://example.com/" + "a" * 50
    color = (25, 196, 125, 255)
    logo = png_bytes(Image.new("RGBA", (400, 400), color))
    d = Design(url=url, logo=logo, logo_scale=25, reserve_logo=reserve, resolution=1200)
    result, meta = render(d, fmt, 640 if fmt == "PREVIEW" else None)
    assert meta["modules"] == 49
    if fmt == "PREVIEW":
        image = Image.open(io.BytesIO(result["logo"])).convert("RGBA")
    elif fmt == "SVG":
        image = Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=result.decode()))).convert("RGBA")
    elif fmt == "PDF":
        with pdfium.PdfDocument(result) as document:
            image = document[0].render(scale=300/72).to_pil().convert("RGBA")
    else:
        image = Image.open(io.BytesIO(result)).convert("RGBA")
    n = 49
    gx, gy, w, h = logo_geometry(d, n)
    scale = image.width / (n+8)
    crop = image.crop((round((gx+.5)*scale), round((gy+.5)*scale),
                       round((gx+w-.5)*scale), round((gy+h-.5)*scale)))
    assert all(max(abs(a-b) for a,b in zip(pixel, color)) <= 5 for pixel in crop.get_flattened_data())
    if fmt != "PREVIEW":
        qr = zxingcpp.read_barcode(image.convert("RGB"))
        assert qr and qr.text == url
    elif reserve:
        assert (d.eye_frame, 26, 26, 5, 5, 255) not in result["ops"]


def test_transparent_logo_reservation_clears_entire_central_alignment():
    d = Design(url="https://example.com/" + "a"*50,
               logo=png_bytes(Image.new("RGBA", (400,400), (0,0,0,0))), resolution=1140)
    data, _ = render(d)
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    # Central 5x5 marker is within a 9.8-module reserved logo rectangle.
    assert image.crop((26*20,26*20,31*20,31*20)).getextrema() == ((255,255),)*4


@pytest.mark.parametrize("fmt", ["PNG", "SVG", "JPG", "PDF"])
@pytest.mark.parametrize("axis", ["Width", "Height"])
def test_square_rounded_wide_wordmark_reference(fmt, axis):
    # Reference has separate rounded squares and a wide, proportional wordmark.
    logo = Image.new("RGBA", (1200,280) if axis=="Width" else (280,1200), "#19C47D")
    d = Design(url="https://example.com/"+"a"*50,
               body="Square Rounded", eye_frame="Square Rounded", eye_ball="Square Rounded",
               logo=png_bytes(logo), logo_axis=axis, logo_scale=70, wide_logo=True, logo_padding=1,
               color="#000000", background_rounding=0, resolution=1600)
    gx,gy,w,h = logo_geometry(d,49)
    assert w/h == pytest.approx(logo.width/logo.height)
    assert max(w,h) > 49*.6  # Wide artwork must no longer be capped at 25% width.
    assert gx>=12 and gy>=12  # Protect timing/finder bands.
    data,_ = render(d,fmt)
    if fmt=="SVG":
        data=resvg_py.svg_to_bytes(svg_string=data.decode())
    if fmt=="PDF":
        with pdfium.PdfDocument(data) as document:
            qr=zxingcpp.read_barcode(document[0].render(scale=300/72).to_pil())
    else:
        qr=zxingcpp.read_barcode(Image.open(io.BytesIO(data)))
    assert qr and qr.text==d.url
    packet,_=render(d,"PREVIEW",640)
    cells=[op for op in packet["ops"] if op[0]=="Square Rounded" and op[3]<1]
    assert cells and all(op[3]==pytest.approx(.92) and op[4]==pytest.approx(.92) for op in cells)
    assert not any(op[0]=="Square Rounded" and op[3]==5 and op[5] for op in packet["ops"]), "Alignment bits should blend into the body, not become extra large eyes"


@pytest.mark.parametrize("value,commit,expected",[
    ("",True,"https://"),("example.com",True,"https://example.com"),
    ("example.com  ",False,"https://example.com"),("example.com. ",False,"https://example.com"),
    ("  ",False,"https://"),("https://example.com  ",False,"https://example.com"),
    ("http://example.com",True,"http://example.com"),("https;//example.com",True,"https://example.com"),
    ("example.com",False,"example.com")])
def test_url_shortcuts(value,commit,expected):
    from qrstudio.url_input import complete_url
    assert complete_url(value,commit)==expected


def test_corrupt_image():
    with pytest.raises(ValueError,match="could not be opened"):
        load_image(b"broken")


def test_warning_low_contrast():
    _,meta=render(Design(color="#EEEEEE",resolution=256))
    assert any("contrast" in note for note in meta["warnings"])


@pytest.mark.asyncio
async def test_background_process_exports():
    import asyncio
    from qrstudio.workers import render_async,shutdown
    try:
        outputs=await asyncio.gather(*(render_async(Design(resolution=512),fmt) for fmt in ("PNG","JPG","SVG","PDF")))
        assert len(outputs)==4
        assert decode(outputs[0][0])==Design().url
    finally:
        shutdown()
