"""Shared QR geometry drawn by Flutter Canvas (Impeller on Android).

Python prepares the matrix and background/logo textures off-thread. Flutter draws
one vector ink path with a GPU gradient shader; no CPU QR bitmap is sent for preview.
Exports deliberately use the portable Pillow renderer for deterministic files.
"""
import math

import flet as ft
import flet.canvas as cv

from .engine import png_bytes
from PIL import Image

K = .5522847498307936


def contour(kind,x,y,w,h,filled=True):
    """Clockwise solids, counterclockwise holes for Flutter's non-zero fill rule."""
    segments=[]
    def line(a,b):
        if a!=b:
            segments.append((a,b,None,None))
    def curve(a,c1,c2,b):
        segments.append((a,b,c1,c2))
    if kind in ("Circle","Dots"):
        rx,ry=w/2,h/2
        cx,cy=x+rx,y+ry
        curve((cx,cy-ry),(cx+rx*K,cy-ry),(cx+rx,cy-ry*K),(cx+rx,cy))
        curve((cx+rx,cy),(cx+rx,cy+ry*K),(cx+rx*K,cy+ry),(cx,cy+ry))
        curve((cx,cy+ry),(cx-rx*K,cy+ry),(cx-rx,cy+ry*K),(cx-rx,cy))
        curve((cx-rx,cy),(cx-rx,cy-ry*K),(cx-rx*K,cy-ry),(cx,cy-ry))
    elif kind=="Diamond":
        pts=[(x+w/2,y),(x+w,y+h/2),(x+w/2,y+h),(x,y+h/2)]
        for i in range(4):
            line(pts[i],pts[(i+1)%4])
    else:
        # Use logical module dimensions for the same radius in GPU and exports.
        # Square Rounded body cells are inset to .92 modules; finder rings and
        # balls use the gentler radius ratio passed via their geometry kind.
        radius=min(w,h)*(.24 if kind=="Square Rounded Body" else .14 if kind=="Square Rounded" else
                           .28 if kind=="Rounded" else .45 if kind=="Horizontal" else .35 if kind=="Leaf" else 0)
        tl,tr,br,bl=(0,radius,0,radius) if kind=="Leaf" else (radius,)*4
        a=(x+tl,y)
        line(a,(x+w-tr,y))
        if tr:
            curve((x+w-tr,y),(x+w-tr+K*tr,y),(x+w,y+tr-K*tr),(x+w,y+tr))
        line((x+w,y+tr),(x+w,y+h-br))
        if br:
            curve((x+w,y+h-br),(x+w,y+h-br+K*br),(x+w-br+K*br,y+h),(x+w-br,y+h))
        line((x+w-br,y+h),(x+bl,y+h))
        if bl:
            curve((x+bl,y+h),(x+bl-K*bl,y+h),(x,y+h-bl+K*bl),(x,y+h-bl))
        line((x,y+h-bl),(x,y+tl))
        if tl:
            curve((x,y+tl),(x,y+tl-K*tl),(x+tl-K*tl,y),(x+tl,y))
    if not filled:
        segments=[(b,a,c2,c1) for a,b,c1,c2 in reversed(segments)]
    elements=[cv.Path.MoveTo(*segments[0][0])]
    for a,b,c1,c2 in segments:
        if c1 is None:
            elements.append(cv.Path.LineTo(*b))
        else:
            elements.append(cv.Path.CubicTo(*c1,*c2,*b))
    elements.append(cv.Path.Close())
    return elements


class GPUPreview:
    def __init__(self,side=320):
        blank=png_bytes(Image.new("RGBA",(1,1)))
        self.bg=ft.Image(src=blank,fit=ft.BoxFit.FILL,exclude_from_semantics=True)
        self.ink=cv.Canvas(key="gpu-qr-canvas")
        self.logo=ft.Image(src=blank,fit=ft.BoxFit.FILL,exclude_from_semantics=True,visible=False)
        self.stack=ft.Stack([self.bg,self.ink,self.logo],width=side,height=side)
        self.control=ft.Container(ft.Semantics(content=self.stack,label="Live QR preview",image=True),key="qr-preview",width=side,height=side)
        self.packet=None
        self.side=side
        self.resize(side)

    def set_packet(self,packet):
        self.packet=packet
        self.bg.src=packet["background"]
        self.logo.visible=packet["logo"] is not None
        if packet["logo"]:
            self.logo.src=packet["logo"]
        self.resize(self.side)

    def resize(self,side):
        self.side=side
        self.control.width=self.control.height=side
        self.stack.width=self.stack.height=side
        for layer in (self.bg,self.ink,self.logo):
            layer.width=layer.height=side
        if self.packet is None:
            return
        packet=self.packet
        scale=side/packet["units"]
        elements=[]
        for kind,x,y,w,h,fill in packet["ops"]:
            if kind=="Square Rounded" and min(w,h)<=1:
                kind="Square Rounded Body"
            elements.extend(contour(kind,x*scale,y*scale,w*scale,h*scale,bool(fill)))
        rad=math.radians(packet["angle"])
        dx,dy=math.cos(rad),math.sin(rad)
        length=abs(dx)+abs(dy)
        shader=ft.PaintLinearGradient(
            begin=ft.Offset(side*(.5-dx*length/2),side*(.5-dy*length/2)),
            end=ft.Offset(side*(.5+dx*length/2),side*(.5+dy*length/2)),
            colors=[packet["color"],packet["color_end"]])
        self.ink.shapes=[cv.Path(elements=elements,paint=ft.Paint(gradient=shader,anti_alias=True,style=ft.PaintingStyle.FILL))]
