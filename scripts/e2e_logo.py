"""Shared real-image fixture and visual assertions for browser/native E2E."""
import io

from PIL import Image, ImageDraw

LOGO_URL = "https://example.com/" + "a" * 50  # Version 8: 49 x 49, central alignment.
LOGO_COLOR = (25, 196, 125)


def make_logo(path, size=(400,400)):
    image = Image.new("RGB", size, LOGO_COLOR)
    draw = ImageDraw.Draw(image)
    corner=max(1,round(min(size)*.1))
    for x, y in ((0, 0), (size[0]-corner, 0), (0, size[1]-corner), (size[0]-corner, size[1]-corner)):
        draw.rectangle((x, y, x + corner-1, y + corner-1), fill="#FFB347")
    image.save(path)


def assert_intact_logo(data):
    """Find the uploaded green artwork, then inspect its whole central 60%.

    Independent decoding alone missed the old bug: the QR could scan while an
    alignment eye was punched through otherwise opaque source artwork.
    """
    image = Image.open(io.BytesIO(data)).convert("RGB")
    mask = Image.new("L", image.size)
    mask.putdata([255 if abs(r-25)<15 and abs(g-196)<15 and abs(b-125)<15 else 0
                  for r, g, b in image.get_flattened_data()])
    box = mask.getbbox()
    assert box is not None, "Uploaded logo must actually appear in the image"
    x1, y1, x2, y2 = box
    w, h = x2-x1, y2-y1
    assert w >= 20 and h >= 20, "Logo must be visible at a useful size"
    center = image.crop((x1+int(w*.2), y1+int(h*.2), x2-int(w*.2), y2-int(h*.2)))
    assert all(abs(r-25)<18 and abs(g-196)<18 and abs(b-125)<18
               for r, g, b in center.get_flattened_data()), "QR alignment marker must never cut through the logo"
    return box
