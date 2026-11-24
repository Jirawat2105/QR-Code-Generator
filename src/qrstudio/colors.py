"""Platform-independent RGB/HSV color state for the advanced picker."""
import colorsys
import math
import re
from dataclasses import dataclass


@dataclass
class ColorState:
    hue: float
    saturation: float
    brightness: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.hue,self.saturation,self.brightness)):
            raise ValueError("Color values must be finite.")
        if not (0<=self.hue<=360 and 0<=self.saturation<=1 and 0<=self.brightness<=1):
            raise ValueError("Color values are outside their range.")

    @classmethod
    def from_rgb(cls,r,g,b):
        if not all(isinstance(v,int) and not isinstance(v,bool) and 0<=v<=255 for v in (r,g,b)):
            raise ValueError("RGB values must be whole numbers from 0 to 255.")
        h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
        return cls(h*360,s,v)

    @property
    def rgb(self):
        return tuple(round(v*255) for v in colorsys.hsv_to_rgb((self.hue%360)/360,self.saturation,self.brightness))

    @property
    def hex(self):
        return "#"+"".join(f"{v:02X}" for v in self.rgb)

    @classmethod
    def from_hex(cls, value):
        if not re.fullmatch(r"#?[0-9a-fA-F]{6}",value):
            raise ValueError("Enter six hex digits, for example #FE6703.")
        value=value.lstrip("#")
        return cls.from_rgb(*(int(value[i:i+2],16) for i in (0,2,4)))

    @classmethod
    def from_rgb(cls, red, green, blue):
        if any(isinstance(v,bool) or not isinstance(v,int) or not 0<=v<=255 for v in (red,green,blue)):
            raise ValueError("RGB values must be whole numbers from 0 to 255.")
        h,s,v=colorsys.rgb_to_hsv(red/255,green/255,blue/255)
        return cls(h*360,s,v)

    @classmethod
    def from_hsv(cls, hue, saturation, brightness):
        if any(not math.isfinite(v) for v in (hue,saturation,brightness)) or not (0<=hue<=360 and 0<=saturation<=100 and 0<=brightness<=100):
            raise ValueError("Use Hue 0–360, Saturation and Brightness 0–100.")
        return cls(hue,saturation/100,brightness/100)

    @property
    def rgb(self):
        return tuple(round(c*255) for c in colorsys.hsv_to_rgb((self.hue%360)/360,self.saturation,self.brightness))

    @property
    def hex(self):
        return "#"+"".join(f"{c:02X}" for c in self.rgb)

    @property
    def hue_hex(self):
        return ColorState(self.hue,1,1).hex
