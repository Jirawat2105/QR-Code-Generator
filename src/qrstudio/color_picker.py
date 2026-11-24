"""Touch-friendly advanced color dialog built from native Flutter controls."""
from __future__ import annotations

import flet as ft

from .colors import ColorState


class AdvancedColorPicker:
    def __init__(self,page,title,current,on_apply):
        self.page,self.on_apply=page,on_apply
        try:
            self.state=ColorState.from_hex(current)
        except ValueError:
            self.state=ColorState.from_hex("#000000")
        self.current=self.state.hex
        self.is_open=False
        self.size=min(236,max(100,(page.width or 390)-120),max(100,(page.height or 844)-360))
        self.fields={}
        self.base=ft.Container(bgcolor=self.state.hue_hex,width=self.size,height=self.size)
        self.sv_cursor=ft.Container(width=12,height=12,border=ft.Border.all(2,"#FFFFFF"),
                                    border_radius=6,shadow=ft.BoxShadow(blur_radius=2,color="#000000"))
        square=ft.Stack([self.base,
            ft.Container(width=self.size,height=self.size,gradient=ft.LinearGradient(
                colors=["#FFFFFFFF","#00FFFFFF"],begin=ft.Alignment.CENTER_LEFT,end=ft.Alignment.CENTER_RIGHT)),
            ft.Container(width=self.size,height=self.size,gradient=ft.LinearGradient(
                colors=["#00000000","#FF000000"],begin=ft.Alignment.TOP_CENTER,end=ft.Alignment.BOTTOM_CENTER)),
            self.sv_cursor],width=self.size,height=self.size,clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.square=square
        sv=ft.Semantics(label="Saturation and brightness",image=True,content=ft.GestureDetector(
            square,on_tap_down=self.pick_sv,on_pan_start=self.pick_sv,on_pan_update=self.pick_sv,
            on_pan_end=self.pick_sv,drag_interval=25))
        self.hue_cursor=ft.Container(width=24,height=7,left=10,border=ft.Border.all(2,"#FFFFFF"))
        hue=ft.Stack([ft.Container(width=24,height=self.size,left=10,gradient=ft.LinearGradient(
            colors=["#FF0000","#FFFF00","#00FF00","#00FFFF","#0000FF","#FF00FF","#FF0000"],
            begin=ft.Alignment.TOP_CENTER,end=ft.Alignment.BOTTOM_CENTER)),self.hue_cursor],
            width=44,height=self.size,clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.hue_stack=hue
        hue=ft.Semantics(label="Hue strip",image=True,content=ft.GestureDetector(
            hue,on_tap_down=self.pick_hue,on_pan_start=self.pick_hue,on_pan_update=self.pick_hue,
            on_pan_end=self.pick_hue,drag_interval=25))
        self.new_swatch=ft.Container(bgcolor=self.current,width=76,height=42,border_radius=6)
        current_swatch=ft.Container(bgcolor=self.current,width=76,height=42,border_radius=6)
        swatches=ft.Row([ft.Column([ft.Text("New",size=12),self.new_swatch],spacing=4),
                         ft.Column([ft.Text("Current",size=12),current_swatch],spacing=4)],spacing=16)
        hex_field=self.field("hex","Hex color")
        rgb=ft.Row([self.field("r","Red"),self.field("g","Green"),self.field("b","Blue")],spacing=8)
        hsv=ft.Row([self.field("h","Hue °"),self.field("s","Sat. %"),self.field("v","Bright. %")],spacing=8)
        self.apply_button=ft.Button("Apply color",on_click=self.apply,bgcolor="#D4F89A",color="#101113")
        width=min(292,max(160,(page.width or 390)-64))
        self.dialog=ft.AlertDialog(title=ft.Text(title,size=18),modal=True,bgcolor="#191B1E",
            inset_padding=16,content_padding=16,
            content=ft.Container(ft.Column([ft.Row([sv,hue],spacing=12,alignment=ft.MainAxisAlignment.CENTER),swatches,hex_field,rgb,hsv,
                ft.Text("Drag the square or hue strip, or enter exact values. Apply to use the new color.",size=11,color="#9B9E9C")],
                spacing=14,scroll=ft.ScrollMode.AUTO,horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                width=width,height=min(560,max(160,(page.height or 844)-220))),
            on_dismiss=lambda e:setattr(self,"is_open",False),
            actions=[ft.TextButton("Cancel",on_click=lambda e:self.close()),self.apply_button])
        self.refresh()

    def field(self,key,label):
        async def edit(e):
            try:
                if key=="hex":
                    state=ColorState.from_hex(e.control.value)
                elif key in "rgb":
                    values=[int(self.fields[k].value) for k in "rgb"]
                    if not all(0<=v<=255 for v in values): raise ValueError("Use 0–255")
                    state=ColorState.from_rgb(*values)
                else:
                    h,s,v=[float(self.fields[k].value) for k in "hsv"]
                    if not (0<=h<=360 and 0<=s<=100 and 0<=v<=100): raise ValueError("Outside range")
                    state=ColorState(h,s/100,v/100)
                self.state=state
                self.refresh(except_field=key)
            except (ValueError,TypeError):
                e.control.error_text="6 hex digits" if key=="hex" else "Use 0–255" if key in "rgb" else "Check range"
                self.apply_button.disabled=True
            self.page.update()
        result=ft.TextField(label=label,key="picker-"+key,text_size=12,filled=True,fill_color="#222428",
                            border_color="#303337",expand=key!="hex",on_change=edit,
                            keyboard_type=ft.KeyboardType.TEXT if key=="hex" else ft.KeyboardType.NUMBER,
                            content_padding=10)
        self.fields[key]=result
        return result

    def refresh(self,except_field=None):
        rgb=self.state.rgb
        values=dict(zip("rgb",map(str,rgb)))
        values.update(hex=self.state.hex,h=f"{self.state.hue:.1f}",
                      s=f"{self.state.saturation*100:.1f}",v=f"{self.state.brightness*100:.1f}")
        for key,control in self.fields.items():
            control.error_text=None
            if key!=except_field: control.value=values[key]
        self.base.bgcolor=ColorState(self.state.hue,1,1).hex
        self.sv_cursor.left=max(0,min(self.size-12,self.state.saturation*self.size-6))
        self.sv_cursor.top=max(0,min(self.size-12,(1-self.state.brightness)*self.size-6))
        self.hue_cursor.top=max(0,min(self.size-7,self.state.hue/360*self.size-3.5))
        self.new_swatch.bgcolor=self.state.hex
        self.apply_button.disabled=False

    async def pick_sv(self,e):
        if e.local_position is None: return
        self.state.saturation=max(0,min(1,e.local_position.x/self.size))
        self.state.brightness=1-max(0,min(1,e.local_position.y/self.size))
        self.refresh()
        self.page.update()

    async def pick_hue(self,e):
        if e.local_position is None: return
        self.state.hue=max(0,min(360,e.local_position.y/self.size*360))
        self.refresh()
        self.page.update()

    async def apply(self,e):
        if self.apply_button.disabled: return
        self.close()
        await self.on_apply(self.state.hex)

    def resize(self):
        # Leave a swatch area available for touch-scrolling below the color
        # plane on short landscape screens. Preserve draft input during IME
        # resizing instead of overwriting partially entered text.
        width=min(292,max(160,(self.page.width or 390)-64))
        self.size=min(236,width-56,max(100,(self.page.height or 844)-360))
        self.dialog.content.width=width
        self.dialog.content.height=min(560,max(160,(self.page.height or 844)-220))
        self.square.width=self.square.height=self.size
        for layer in self.square.controls[:3]:
            layer.width=layer.height=self.size
        self.hue_stack.height=self.size
        self.hue_stack.controls[0].height=self.size
        self.sv_cursor.left=max(0,min(self.size-12,self.state.saturation*self.size-6))
        self.sv_cursor.top=max(0,min(self.size-12,(1-self.state.brightness)*self.size-6))
        self.hue_cursor.top=max(0,min(self.size-7,self.state.hue/360*self.size-3.5))

    def close(self):
        self.is_open=False
        self.page.pop_dialog()

    def open(self):
        self.is_open=True
        self.resize()
        self.page.show_dialog(self.dialog)
