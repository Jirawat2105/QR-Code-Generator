"""Portable QR renderer. No browser, remote API, or platform-specific libraries."""
from __future__ import annotations

import base64
import io
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

import qrcode
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from qrcode.exceptions import DataOverflowError

BODY_SHAPES = ("Square", "Rounded", "Dots", "Diamond", "Horizontal")
FRAME_SHAPES = ("Square", "Rounded", "Circle", "Leaf")
BALL_SHAPES = ("Square", "Rounded", "Circle", "Diamond")
FORMATS = ("PNG", "SVG", "PDF", "JPG")
MAX_IMAGE_BYTES = 16 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000


@dataclass(frozen=True)
class Design:
    url: str = "https://example.com"
    minimalist: bool = False
    body: str = "Rounded"
    eye_frame: str = "Rounded"
    eye_ball: str = "Rounded"
    color_mode: str = "Plain"
    color: str = "#172033"
    color_end: str = "#7957D5"
    angle: int = 45
    logo: bytes | None = None
    logo_scale: int = 20
    logo_axis: str = "Width"
    reserve_logo: bool = True
    logo_padding: int = 2
    background_mode: str = "Plain"
    background: str = "#FFFFFF"
    background_end: str = "#E6DFFF"
    background_image: bytes | None = None
    background_opacity: int = 100
    background_rounding: int = 8
    edge_blur: int = 0
    edge_opacity: int = 100
    resolution: int = 2048

    def validate(self) -> None:
        try:
            url = urlsplit(self.url.strip())
            valid = url.scheme.lower() in ("http", "https") and bool(url.hostname)
            _ = url.port
        except ValueError:
            valid = False
        if not valid or any(c.isspace() or ord(c) < 32 for c in self.url):
            raise ValueError("Enter a complete URL, for example https://example.com")
        if len(self.url.encode("utf-8")) > 1200:
            raise ValueError("This URL is too long. Please use a shorter link (up to 1,200 bytes).")
        for c in (self.color, self.color_end, self.background, self.background_end):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
                raise ValueError("Colors must use six-digit hex, for example #172033.")
        for field, values in (("body", BODY_SHAPES), ("eye_frame", FRAME_SHAPES),
                              ("eye_ball", BALL_SHAPES), ("color_mode", ("Plain", "Gradient")),
                              ("background_mode", ("Plain", "Gradient", "Image")),
                              ("logo_axis", ("Width", "Height"))):
            if getattr(self, field) not in values:
                raise ValueError(f"Invalid {field.replace('_', ' ')}.")
        for field, low, high in (("resolution", 256, 8192), ("logo_scale", 5, 40),
                                 ("background_opacity", 0, 100), ("background_rounding", 0, 25),
                                 ("edge_blur", 0, 20), ("edge_opacity", 0, 100),
                                 ("logo_padding", 0, 5), ("angle", 0, 360)):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{field.replace('_', ' ').capitalize()} must be {low}–{high}.")


def load_image(data: bytes) -> Image.Image:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Choose an image smaller than 16 MB.")
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.width * img.height > 25_000_000:
                raise ValueError("Choose an image smaller than 25 megapixels.")
            return ImageOps.exif_transpose(img).convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("This image could not be opened. Use PNG, JPG or WebP.") from exc


def normalize_image(data: bytes) -> bytes:
    img = load_image(data)
    img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    return png_bytes(img)


def png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


@lru_cache(maxsize=48)
def qr_matrix(url: str, compact: bool = False):
    correction = qrcode.constants.ERROR_CORRECT_M if compact else qrcode.constants.ERROR_CORRECT_H
    qr = qrcode.QRCode(error_correction=correction, border=0)
    qr.add_data(url.strip(), optimize=0)
    try:
        qr.make(fit=True)
    except DataOverflowError as exc:
        raise ValueError("This link is too long for a QR code. Please shorten it.") from exc
    # Preserve functional modules when clearing data modules beneath a logo.
    blank = qrcode.QRCode(version=qr.version, border=0)
    n = qr.modules_count
    blank.modules_count = n
    blank.modules = [[None] * n for _ in range(n)]
    blank.setup_position_probe_pattern(0, 0)
    blank.setup_position_probe_pattern(n - 7, 0)
    blank.setup_position_probe_pattern(0, n - 7)
    blank.setup_position_adjust_pattern()
    blank.setup_timing_pattern()
    blank.setup_type_info(True, 0)
    if qr.version >= 7:
        blank.setup_type_number(True)
    return qr.modules, [[v is not None for v in row] for row in blank.modules], qr.version


def logo_geometry(d: Design, n: int):
    """Logo dimensions in QR modules, referenced to the QR area excluding quiet zone."""
    if not d.logo:
        return None
    img = load_image(d.logo)
    side = n * d.logo_scale / 100
    w, h = (side, side * img.height / img.width) if d.logo_axis == "Width" else (side * img.width / img.height, side)
    # Fit BOTH dimensions with one proportional transform. An unusually wide/tall
    # source must never fail simply because the other axis exceeds the safe area.
    factor = min(1.0, n * .25 / max(w, h))
    w, h = w * factor, h * factor
    return ((n - w) / 2 + 4, (n - h) / 2 + 4, w, h)


class Shapes:
    """One geometry stream feeds both raster masks and real SVG vector shapes."""
    def __init__(self, size: int, units: int, record_only=False):
        self.scale = size / units
        self.record_only = record_only
        self.ops = []
        self.mask = None if record_only else Image.new("L", (size, size))
        self.draw = None if record_only else ImageDraw.Draw(self.mask)
        self.svg: list[str] = []

    def shape(self, kind, x, y, w, h, fill=255):
        self.ops.append((kind, x, y, w, h, fill))
        if self.record_only:
            return
        s = self.scale
        # Pillow boxes include both endpoints; right/bottom epsilon avoids overlaps.
        box = (round(x*s), round(y*s), round((x+w)*s)-1, round((y+h)*s)-1)
        if box[2] < box[0] or box[3] < box[1]:
            return
        color = "white" if fill else "black"
        if kind in ("Circle", "Dots"):
            self.draw.ellipse(box, fill=fill)
            tag = f'<ellipse cx="{x+w/2:.4f}" cy="{y+h/2:.4f}" rx="{w/2:.4f}" ry="{h/2:.4f}" fill="{color}"/>'
        elif kind == "Diamond":
            pts = [(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)]
            self.draw.polygon([(round(a*s),round(b*s)) for a,b in pts], fill=fill)
            tag = f'<polygon points="{" ".join(f"{a:.4f},{b:.4f}" for a,b in pts)}" fill="{color}"/>'
        elif kind == "Leaf":
            r = w * .35
            # Opposite rounded corners, in both raster and SVG.
            self.draw.rounded_rectangle(box, radius=r*s, fill=fill)
            self.draw.rectangle((box[0],box[1],round((x+r)*s),round((y+r)*s)), fill=fill)
            self.draw.rectangle((round((x+w-r)*s),round((y+h-r)*s),box[2],box[3]), fill=fill)
            tag = (f'<path d="M{x},{y} H{x+w-r} A{r},{r} 0 0 1 {x+w},{y+r} V{y+h} '
                   f'H{x+r} A{r},{r} 0 0 1 {x},{y+h-r} Z" fill="{color}"/>')
        else:
            r = min(w,h) * (.28 if kind == "Rounded" else .45 if kind == "Horizontal" else 0)
            self.draw.rounded_rectangle(box, radius=r*s, fill=fill)
            tag = f'<rect x="{x:.4f}" y="{y:.4f}" width="{w:.4f}" height="{h:.4f}" rx="{r:.4f}" fill="{color}"/>'
        self.svg.append(tag)


@lru_cache(maxsize=32)
def _gradient_sample(a: str, b: str, angle: int) -> bytes:
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    span = abs(dx)+abs(dy)
    # Affine interpolation + lookup tables execute in Pillow's native code,
    # avoiding 65,536 Python pixel iterations for every gradient/worker.
    ramp = Image.linear_gradient("L").transform(
        (256,256), Image.Transform.AFFINE,
        (0,0,128,dx/span,dy/span,127.5-(dx+dy)*127.5/span),
        resample=Image.Resampling.BILINEAR)
    return ImageOps.colorize(ramp,a,b).tobytes()


def gradient(a, b, angle, size):
    if a == b:
        return Image.new("RGB", (size,size), a)
    return Image.frombytes("RGB", (256,256), _gradient_sample(a,b,angle)).resize((size,size), Image.Resampling.BILINEAR)


def background_layer(d: Design, size: int, units: int):
    if d.background_mode == "Image" and d.background_image:
        bg = ImageOps.fit(load_image(d.background_image), (size,size), method=Image.Resampling.LANCZOS)
    else:
        bg = gradient(d.background, d.background_end if d.background_mode == "Gradient" else d.background, d.angle, size).convert("RGBA")
    mask = Image.new("L", (size,size))
    draw = ImageDraw.Draw(mask)
    # Keep the full four-module quiet zone and all QR cells inside the background.
    radius = min(size * d.background_rounding/100, size * 3.8/units)
    draw.rounded_rectangle((0,0,size-1,size-1), radius=radius, fill=255)
    if d.edge_blur:
        inset = min(size*d.edge_blur/100, size*2.5/units)
        inner = Image.new("L", (size,size))
        ImageDraw.Draw(inner).rounded_rectangle((inset,inset,size-inset-1,size-inset-1), radius=radius, fill=255)
        inner = inner.filter(ImageFilter.GaussianBlur(inset*.48))
        # edge_opacity specifies opacity at the outer edge; interior remains opaque.
        fade = inner.point(lambda v: round(d.edge_opacity*2.55 + v*(1-d.edge_opacity/100)))
        mask = ImageChops.multiply(mask, fade)
    mask = mask.point(lambda v: round(v*d.background_opacity/100))
    bg.putalpha(ImageChops.multiply(bg.getchannel("A"), mask))
    return bg


def render(d: Design, fmt: str = "PNG", preview_size: int | None = None) -> tuple[bytes, dict]:
    d.validate()
    fmt = fmt.upper()
    vector_preview = fmt == "PREVIEW"
    if fmt not in FORMATS and not vector_preview:
        raise ValueError("Choose PNG, SVG, PDF or JPG.")
    compact = d.minimalist and not d.logo
    matrix, functional, version = qr_matrix(d.url, compact)
    n = len(matrix)
    units = n+8
    output_size = preview_size or d.resolution
    # At export sizes >= 1024 native sampling already resolves even dense QR cells.
    work_size = min(8192, output_size * (2 if output_size < 1024 and not vector_preview else 1))
    shapes = Shapes(work_size, units, record_only=vector_preview)
    geo = logo_geometry(d, n)
    frame, ball, body = d.eye_frame, d.eye_ball, d.body
    # Alignment markers are small eyes: style their rings as a whole instead of
    # leaving a conspicuous square block among dots/diamonds (the reported bug).
    positions = qrcode.util.pattern_position(version)
    alignments = [(x,y) for y in positions for x in positions
                  if not ((x<9 and y<9) or (x>n-10 and y<9) or (x<9 and y>n-10))]
    def in_finder(x,y):
        return (x<7 and y<7) or (x>=n-7 and y<7) or (x<7 and y>=n-7)
    alignment_cells = {(x+dx,y+dy) for x,y in alignments for dx in range(-2,3) for dy in range(-2,3)}
    def reserved(x,y):
        if not (geo and d.reserve_logo) or functional[y][x]:
            return False
        gx,gy,w,h = geo
        p = d.logo_padding
        return x+5>gx-p and x+4<gx+w+p and y+5>gy-p and y+4<gy+h+p
    for y,row in enumerate(matrix):
        x = 0
        while x<n:
            if not row[x] or in_finder(x,y) or (x,y) in alignment_cells or reserved(x,y):
                x += 1
                continue
            kind = body
            # A full-cell diamond has 50% ink coverage. Insetting it further made
            # small SVG modules too light for format-bit detection after rasterizing.
            w, inset = 1, .08 if kind == "Dots" else 0
            if kind == "Horizontal":
                while x+w<n and row[x+w] and not functional[y][x+w] and not in_finder(x+w,y) and not reserved(x+w,y):
                    w += 1
            shapes.shape(kind,x+4+inset,y+4+inset,w-inset*2,1-inset*2)
            x += w
    for x,y in ((4,4),(n-3,4),(4,n-3)):
        shapes.shape(frame,x,y,7,7)
        shapes.shape(frame,x+1,y+1,5,5,0)
        # A diamond has half the ink area of a square. A small optical expansion
        # keeps finder detection stable after SVG antialiasing, without filling
        # its white ring or changing the selected diamond silhouette.
        ball_side=3.3 if ball=="Diamond" else 3
        shapes.shape(ball,x+(7-ball_side)/2,y+(7-ball_side)/2,ball_side,ball_side)
    for x,y in alignments:
        shapes.shape(frame,x+2,y+2,5,5)
        shapes.shape(frame,x+3,y+3,3,3,0)
        shapes.shape(ball,x+4,y+4,1,1)
    if not vector_preview:
        foreground = gradient(d.color, d.color_end if d.color_mode=="Gradient" else d.color, d.angle, work_size).convert("RGBA")
        foreground.putalpha(shapes.mask)
    bg = background_layer(d, work_size, units)
    raster = None if vector_preview else Image.alpha_composite(bg,foreground)
    logo_overlay = None
    logo_svg = ""
    if geo:
        gx,gy,w,h=geo
        logo = load_image(d.logo)
        # A single proportional transform; do not crop or stretch source artwork.
        source_logo=png_bytes(logo)
        logo = logo.resize((max(1,round(w*shapes.scale)),max(1,round(h*shapes.scale))),Image.Resampling.LANCZOS)
        # Cut functional cells out of the logo alpha instead of allocating a full
        # export-sized image per cell. This also preserves photo/gradient backgrounds.
        alpha=logo.getchannel("A")
        safe=ImageDraw.Draw(alpha)
        cuts=[]
        origin_x,origin_y=round(gx*shapes.scale),round(gy*shapes.scale)
        for y in range(n):
            for x in range(n):
                if functional[y][x] and x+5>gx and x+4<gx+w and y+5>gy and y+4<gy+h:
                    safe.rectangle((round((x+4)*shapes.scale)-origin_x,round((y+4)*shapes.scale)-origin_y,
                                    round((x+5)*shapes.scale)-origin_x-1,round((y+5)*shapes.scale)-origin_y-1),fill=0)
                    cuts.append(f'<rect x="{x+4}" y="{y+4}" width="1" height="1" fill="black"/>')
        logo.putalpha(alpha)
        if vector_preview:
            layer = Image.new("RGBA", (work_size, work_size))
            layer.alpha_composite(logo, (origin_x,origin_y))
            logo_overlay = png_bytes(layer)
        else:
            raster.alpha_composite(logo,(origin_x,origin_y))
        logo_svg=(f'<defs><mask id="logo-safe" maskUnits="userSpaceOnUse" x="0" y="0" width="{units}" height="{units}">'
                  f'<rect width="{units}" height="{units}" fill="white"/>{"".join(cuts)}</mask></defs>'
                  f'<image x="{gx}" y="{gy}" width="{w}" height="{h}" mask="url(#logo-safe)" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{base64.b64encode(source_logo).decode()}"/>')
    notes = []
    def lum(c):
        vals = [v/255 for v in bytes.fromhex(c[1:])]
        vals = [v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in vals]
        return sum(a*b for a,b in zip(vals,(.2126,.7152,.0722)))
    colors = (d.color,d.color_end) if d.color_mode=="Gradient" else (d.color,)
    contrast = min((lum(d.background)+.05)/(lum(c)+.05) for c in colors)
    if contrast<4.5:
        notes.append("Low contrast: use darker QR colors on a lighter background.")
    if d.background_opacity<100:
        notes.append("Transparency depends on the surface behind your QR. Test on its final background.")
    if d.background_mode == "Image":
        notes.append("Photo backgrounds may reduce readability. Keep the area under the QR light and simple.")
    if geo and (d.logo_scale>25 or geo[2]*geo[3]/n**2>.08):
        notes.append("Large logos can reduce readability. Test a printed sample or reduce the logo scale.")
    if geo:
        effective = (geo[2] if d.logo_axis == "Width" else geo[3]) / n * 100
        if effective < d.logo_scale-.05:
            notes.append(f"Logo auto-fitted to {effective:.1f}% {d.logo_axis.lower()} while preserving its original aspect ratio.")
    if n*8>output_size:
        notes.append("This URL creates a dense QR. Choose a higher resolution for sharp modules.")
    meta = {"version":version,"modules":n,"ecc":"M (~15%)" if compact else "H (~30%)","warnings":notes,"contrast":round(contrast,1),"width":output_size,"height":output_size}
    if vector_preview:
        return {"background":png_bytes(bg), "logo":logo_overlay, "ops":shapes.ops, "units":units,
                "color":d.color, "color_end":d.color_end if d.color_mode=="Gradient" else d.color,
                "angle":d.angle}, meta
    if fmt=="SVG":
        # Background effects are a self-contained raster layer, QR geometry is vector.
        bg_small = bg if work_size<=2048 else background_layer(d,2048,units)
        bg_uri=base64.b64encode(png_bytes(bg_small)).decode()
        rad=math.radians(d.angle)
        dx,dy=math.cos(rad),math.sin(rad)
        length=abs(dx)+abs(dy)
        # Endpoints match the projected linear interpolation in the raster renderer.
        x1,y1=.5-dx*length/2,.5-dy*length/2
        x2,y2=.5+dx*length/2,.5+dy*length/2
        end=d.color_end if d.color_mode=="Gradient" else d.color
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{d.resolution}" height="{d.resolution}" viewBox="0 0 {units} {units}">'
             f'<title>QR code for {escape(d.url)}</title><defs>'
             f'<linearGradient id="ink" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"><stop stop-color="{d.color}"/><stop offset="1" stop-color="{end}"/></linearGradient>'
             f'<mask id="qr" maskUnits="userSpaceOnUse" x="0" y="0" width="{units}" height="{units}"><rect width="{units}" height="{units}" fill="black"/>{"".join(shapes.svg)}</mask></defs>'
             f'<image width="{units}" height="{units}" href="data:image/png;base64,{bg_uri}"/>'
             f'<rect width="{units}" height="{units}" fill="url(#ink)" mask="url(#qr)"/>{logo_svg}</svg>')
        return svg.encode(),meta
    if work_size!=output_size:
        raster=raster.resize((output_size,output_size),Image.Resampling.LANCZOS)
    if fmt in ("PDF","JPG"):
        white=Image.new("RGB",raster.size,"white")
        white.paste(raster,mask=raster.getchannel("A"))
        raster=white
    out=io.BytesIO()
    if fmt=="PDF":
        raster.save(out,"PDF",resolution=300)
    elif fmt=="JPG":
        raster.save(out,"JPEG",quality=97,subsampling=0,dpi=(300,300))
    else:
        raster.save(out,"PNG",dpi=(300,300))
    return out.getvalue(),meta
