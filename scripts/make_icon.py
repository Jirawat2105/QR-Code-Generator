"""Generate our geometric app icon without external artwork or fonts."""
from pathlib import Path
from PIL import Image,ImageDraw

out=Path(__file__).resolve().parents[1]/"src"/"assets"
out.mkdir(exist_ok=True)
im=Image.new("RGBA",(512,512),"#101113")
d=ImageDraw.Draw(im)
d.rounded_rectangle((44,44,468,468),radius=108,fill="#D4F89A")
for x,y in ((112,112),(290,112),(112,290)):
    d.rounded_rectangle((x,y,x+110,y+110),radius=24,fill="#172033")
    d.rounded_rectangle((x+20,y+20,x+90,y+90),radius=12,fill="#D4F89A")
    d.rounded_rectangle((x+38,y+38,x+72,y+72),radius=5,fill="#172033")
for x,y in ((260,260),(304,260),(348,260),(260,304),(348,304),(392,304),(304,348),(348,392),(392,392),(260,392)):
    d.rounded_rectangle((x,y,x+26,y+26),radius=5,fill="#172033")
im.save(out/"icon.png")
