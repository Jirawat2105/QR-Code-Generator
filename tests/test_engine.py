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


@pytest.mark.parametrize("url",["","hello","ftp://example.com","https://","https://a b.com","https://[bad","https://example.com:bad"])
def test_url_required(url):
    with pytest.raises(ValueError):
        render(Design(url=url))


@pytest.mark.parametrize("options",[{"resolution":0},{"resolution":8193},{"resolution":True},{"color":"red"},{"logo_scale":50},{"body":"wrong"},{"background_opacity":101}])
def test_invalid_settings(options):
    with pytest.raises(ValueError):
        render(replace(Design(),**options))


def test_oversized_logo_is_proportionally_auto_fitted(logo):
    d=Design(logo=logo,logo_axis="Height",logo_scale=40,resolution=768)
    n=len(qr_matrix(d.url)[0])
    _,_,w,h=logo_geometry(d,n)
    assert w/h==pytest.approx(2.5)
    assert max(w,h)<=n*.25+1e-9
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
