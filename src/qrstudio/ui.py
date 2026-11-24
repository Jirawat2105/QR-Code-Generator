from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from dataclasses import replace
from pathlib import Path

import flet as ft

from .engine import (BALL_SHAPES, BODY_SHAPES, FORMATS, FRAME_SHAPES, Design,
                     normalize_image, png_bytes, render)
from .workers import render_async
from .gpu_preview import GPUPreview
from .url_input import complete_url

BG = "#101113"
PANEL = "#191B1E"
FIELD = "#222428"
LINE = "#303337"
TEXT = "#F1F2EE"
MUTED = "#9B9E9C"
ACCENT = "#D4F89A"


def text(value, size=13, color=TEXT, weight=None, **kwargs):
    return ft.Text(value, size=size, color=color, weight=weight, **kwargs)


def pill(label, color=ACCENT):
    return ft.Container(text(label, 10, color, ft.FontWeight.W_600), bgcolor="#252D23", padding=ft.Padding.symmetric(horizontal=10, vertical=5), border_radius=20)


class Studio:
    def __init__(self, page: ft.Page):
        self.page = page
        self.design = Design()
        self.controls = {}
        self.shape_tiles = {}
        self.color_swatches = {}
        self.pending = None
        self.generation = 0
        self.valid = False
        self.exporting = False
        self.mobile = None
        self.layout_mode = None
        self.picker = ft.FilePicker()
        self.logo_name = text("PNG, JPG or WebP · original proportions", 11, MUTED)
        self.bg_name = text("Choose a background image", 11, MUTED)
        self.last_data = None
        self.meta = {}

    def field(self, name, label, value=None, **kwargs):
        field = ft.TextField(key=name, label=label, value=str(value if value is not None else getattr(self.design, name)),
                             text_size=13, filled=True, fill_color=FIELD, color=TEXT,
                             border=ft.InputBorder.OUTLINE, border_color=LINE,
                             focused_border_color=ACCENT, border_radius=10,
                             on_change=self.change, **kwargs)
        self.controls[name] = field
        return field

    def dropdown(self, name, label, options):
        field = ft.Dropdown(key=name, label=label, value=getattr(self.design,name),
                            options=[ft.DropdownOption(o) for o in options],
            on_select=self.change, filled=True, fill_color=FIELD, tooltip=label,
                            border_color=LINE, border_radius=10, text_size=13, color=TEXT,
                            content_padding=12, expand=True)
        self.controls[name] = field
        return field

    def slider(self, name, label, low, high, suffix="%"):
        value = text(f"{getattr(self.design,name)}{suffix}", 12, ACCENT)
        async def changed(e):
            value.value = f"{round(e.control.value)}{suffix}"
            await self.change(e)
        slider = ft.Slider(key=name, min=low, max=high, divisions=high-low,
                           value=getattr(self.design,name), active_color=ACCENT,
                           inactive_color=LINE, label="{value}"+suffix, on_change=changed)
        self.controls[name] = slider
        self.controls[name+"_readout"] = value
        return ft.Column([ft.Row([text(label,12,MUTED,expand=True),value]),slider],spacing=0)

    def toggle(self, name, title, subtitle):
        switch = ft.Switch(key=name,value=getattr(self.design,name),active_color=BG,
                           active_track_color=ACCENT,on_change=self.change,
                           tooltip=title)
        self.controls[name]=switch
        return ft.Row([ft.Column([text(title,13),text(subtitle,11,MUTED)],spacing=3,expand=True),switch])

    def shape_picker(self, name, label, options):
        icons={"Square":ft.Icons.CROP_SQUARE_ROUNDED,"Rounded":ft.Icons.ROUNDED_CORNER,
               "Square Rounded":ft.Icons.ROUNDED_CORNER,
               "Dots":ft.Icons.APPS_ROUNDED,"Circle":ft.Icons.CIRCLE_OUTLINED,
               "Diamond":ft.Icons.DIAMOND_OUTLINED,"Leaf":ft.Icons.SPA_OUTLINED,
               "Horizontal":ft.Icons.DRAG_HANDLE_ROUNDED}
        tiles=[]
        for option in options:
            async def select(e, field=name, choice=option):
                self.design=replace(self.design,**{field:choice})
                self.sync_shapes()
                self.schedule()
            selected=getattr(self.design,name)==option
            tile=ft.Container(ft.Column([ft.Icon(icons[option],size=22,color=ACCENT if selected else MUTED),
                                         text(option,10,ACCENT if selected else MUTED)],
                                        spacing=7,horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                              key=f"{name}-{option.lower()}",expand=True,padding=ft.Padding.symmetric(vertical=13,horizontal=3),
                              border_radius=10,bgcolor="#293124" if selected else FIELD,
                              border=ft.Border.all(1,ACCENT if selected else LINE),
                              on_click=select,tooltip=f"{label}: {option}",ink=True)
            tiles.append(tile)
            self.shape_tiles[(name,option)]=tile
        group=ft.Column([text(label,12,MUTED),
                         *[ft.Row(tiles[i:i+3],spacing=7) for i in range(0,len(tiles),3)]],spacing=8)
        self.controls[name+"_group"]=group
        return group

    def sync_shapes(self):
        for (name,option),tile in self.shape_tiles.items():
            chosen=getattr(self.design,name)==option
            tile.bgcolor="#293124" if chosen else FIELD
            tile.border=ft.Border.all(1,ACCENT if chosen else LINE)
            tile.content.controls[0].color=ACCENT if chosen else MUTED
            tile.content.controls[1].color=ACCENT if chosen else MUTED

    def card(self, number, title, subtitle, children):
        return ft.Container(ft.Column([
            ft.Row([ft.Container(text(number,11,ACCENT),width=27,height=27,alignment=ft.Alignment.CENTER,
                                 bgcolor="#293124",border_radius=8),
                    text(title,16,weight=ft.FontWeight.W_600)],spacing=10),
            text(subtitle,11,MUTED), *children],spacing=17,horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=PANEL,border=ft.Border.all(1,LINE),border_radius=16,padding=22)

    def color_pair(self, prefix=""):
        a,b=("color","color_end") if not prefix else ("background","background_end")
        first=self.field(a,"Color" if not prefix else "Background color",expand=True,max_length=7)
        second=self.field(b,"End color",expand=True,max_length=7)
        second.visible=False
        row=ft.Row([first,second],spacing=10)
        return row

    def build(self):
        p=self.page
        p.title="QR Generator"
        p.bgcolor=BG
        p.padding=0
        p.spacing=0
        p.theme_mode=ft.ThemeMode.DARK
        p.theme=ft.Theme(color_scheme_seed=ACCENT,font_family="Segoe UI",use_material3=True)
        p.window.width=1280
        p.window.height=900
        p.window.min_width=360
        p.window.min_height=680
        url=self.field("url","Destination URL *",hint_text="https://example.com",prefix_icon=ft.Icons.LINK_ROUNDED,
                       keyboard_type=ft.KeyboardType.URL,autocorrect=False,enable_suggestions=False,
                       on_blur=self.complete_url_field)
        link_card=self.card("01","Where should it go?","A website, a portfolio, a memory. Start with your link.",[
            url,self.toggle("minimalist","Minimalist QR","Fewer modules, with or without a logo. Every style stays editable.")])
        shape_card=self.card("02","Find your shape","The little details make it yours.",[
            self.shape_picker("body","Body shape",BODY_SHAPES),
            self.shape_picker("eye_frame","Eye frame",FRAME_SHAPES),
            self.shape_picker("eye_ball","Eye ball",BALL_SHAPES)])
        palette=ft.Row(spacing=8)
        for label,first,last in (("Ink","#172033","#7957D5"),("Forest","#163E35","#387E65"),
                                  ("Violet","#38215E","#7957D5"),("Ocean","#073B5A","#137DA3"),
                                  ("Rose","#671F3A","#A1476A"),("Mono","#111111","#555555")):
            async def choose(e,a=first,b=last):
                self.design=replace(self.design,color=a,color_end=b)
                self.controls["color"].value=a
                self.controls["color_end"].value=b
                self.schedule()
            palette.controls.append(ft.Container(width=32,height=32,bgcolor=first,border_radius=16,
                                                 border=ft.Border.all(2,"#5D6165"),on_click=choose,
                                                 tooltip=label,key="palette-"+label.lower(),ink=True))
        color_card=self.card("03","Set the mood","Start with a palette, or enter your own hex colors.",[
            self.dropdown("color_mode","Ink style",["Plain","Gradient"]),palette,self.color_pair(),
            self.slider("angle","Gradient direction",0,360,"°")])
        logo_buttons=ft.Row([ft.OutlinedButton("Choose logo",icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
                                              on_click=self.pick_logo,key="choose-logo",expand=True),
                             ft.IconButton(icon=ft.Icon(ft.Icons.CLOSE_ROUNDED,semantics_label="Remove logo"),tooltip="Remove logo",on_click=self.remove_logo,key="remove-logo")])
        logo_card=self.card("04","Make it recognizably you","Your original logo. No cropping. No stretching.",[
            logo_buttons,self.logo_name,
            self.dropdown("logo_axis","Scale relative to QR",["Width","Height"]),
            self.toggle("wide_logo","Wide wordmark","Allow a wide or tall logo across the center. Test before printing."),
            self.slider("logo_scale","Logo size · % of QR area",5,80),
            self.toggle("reserve_logo","Reserve space for logo","Clear a dedicated area beneath your logo."),
            self.slider("logo_padding","Space around logo",0,5," modules")])
        self.bg_image_group=ft.Column([
            ft.OutlinedButton("Choose background",icon=ft.Icons.IMAGE_OUTLINED,on_click=self.pick_background,key="choose-background"),
            self.bg_name],visible=False,spacing=7)
        background_card=self.card("05","Give it a background","Solid, gradient or a photo. Transparency is up to you.",[
            self.dropdown("background_mode","Background style",["Plain","Gradient","Image"]),
            self.color_pair("bg"),self.bg_image_group,
            self.slider("background_opacity","Background opacity",0,100),
            self.slider("background_rounding","Rounded corners",0,25),
            self.slider("edge_blur","Soft edge",0,20),
            self.slider("edge_opacity","Outer edge opacity",0,100),
            text("Soft edges affect the background only; QR modules stay sharp.",11,MUTED)])
        self.setting_cards=[link_card,shape_card,color_card,logo_card,background_card]
        self.editor=ft.Column(self.setting_cards.copy(),spacing=14,key=ft.ScrollKey("editor-start"))

        self.gpu_preview=GPUPreview()
        self.preview_image=self.gpu_preview.control
        self.status=pill("PREPARING")
        self.status.key="preview-status"
        self.preview_meta=text("High error correction · generous quiet zone",11,MUTED,text_align=ft.TextAlign.CENTER)
        self.warning=text("",11,"#EBCB89",key="design-warning",visible=False)
        self.error=text("",12,"#FFA5A5",key="design-error",visible=False)
        # A checkerboard makes alpha visible without changing the actual exported background.
        from PIL import Image,ImageDraw
        board=Image.new("RGB",(384,384),"#E5E7E2")
        draw=ImageDraw.Draw(board)
        for yy in range(0,384,12):
            for xx in range(0,384,12):
                if (xx//12+yy//12)%2:
                    draw.rectangle((xx,yy,xx+11,yy+11),fill="#D6D9D3")
        self.preview_surface=ft.Container(ft.Stack([
            ft.Image(src=png_bytes(board),width=384,height=384,fit=ft.BoxFit.COVER),
            ft.Container(self.preview_image,alignment=ft.Alignment.CENTER,padding=24,expand=True)
        ],width=384,height=384),border_radius=18,clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
        self.resolution=self.field("resolution","Export resolution (px)",keyboard_type=ft.KeyboardType.NUMBER)
        self.format=ft.Dropdown(key="export-format",label="File format",value="PNG",tooltip="File format",
                                 options=[ft.DropdownOption(v) for v in FORMATS],
                                 filled=True,fill_color=FIELD,border_color=LINE,border_radius=10,
                                 text_size=13,expand=True,on_select=self.format_changed)
        self.format_help=text("PNG · transparent background supported",11,MUTED)
        self.export_button=ft.Button("Export QR code",icon=ft.Icons.DOWNLOAD_ROUNDED,
                                     key="export",on_click=self.export,disabled=True,
                                     bgcolor=ACCENT,color=BG,height=49,expand=True,
                                     style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=11),text_style=ft.TextStyle(weight=ft.FontWeight.W_600)))
        self.zip_button=ft.OutlinedButton("Export all formats (.zip)",icon=ft.Icons.FOLDER_ZIP_OUTLINED,
                                          key="export-all",on_click=self.export_all,disabled=True,expand=True)
        self.export_status=text("",11,ACCENT,key="export-status",selectable=True)
        self.preview_panel=ft.Container(ft.Column([
            ft.Row([text("Your QR, live.",18,weight=ft.FontWeight.W_600),ft.Container(expand=True),self.status]),
            text("Live vector preview · GPU rendering",11,MUTED),
            ft.Container(self.preview_surface,alignment=ft.Alignment.CENTER,padding=ft.Padding.symmetric(vertical=8)),
            self.preview_meta,self.error,self.warning,ft.Divider(color=LINE,height=15),
            ft.Row([text("Ready when you are.",15,weight=ft.FontWeight.W_600),pill("EXPORT")]),
            self.resolution,ft.Row([self.format]),self.format_help,
            ft.Row([self.export_button]),ft.Row([self.zip_button]),self.export_status,
            text("No sign-up. No expiring links. Your files stay yours.",10,MUTED,text_align=ft.TextAlign.CENTER)
        ],spacing=13,horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            padding=24,bgcolor=PANEL,border=ft.Border.all(1,LINE),border_radius=18)
        self.editor_host=ft.Container(self.editor,expand=6)
        self.preview_host=ft.Container(self.preview_panel,expand=5)
        self.workspace=ft.Container(expand=True)
        self.header_hint=text("A little code. A world of possibilities.",12,MUTED)
        self.header=ft.Container(ft.Row([
            ft.Container(ft.Icon(ft.Icons.QR_CODE_2_ROUNDED,color=BG,size=25),width=41,height=41,
                         bgcolor=ACCENT,border_radius=11,alignment=ft.Alignment.CENTER,
                         on_click=self.show_credits,tooltip="Credits",key="app-credits",ink=True),
            ft.Column([text("QR Generator",17,weight=ft.FontWeight.W_700),text("CREATE · CUSTOMIZE",9,MUTED)],spacing=0),
            ft.Container(expand=True),self.header_hint,
            ft.IconButton(ft.Icons.RESTART_ALT_ROUNDED,tooltip="Reset design",key="reset",on_click=self.reset)],spacing=12),
            padding=ft.Padding.symmetric(horizontal=28,vertical=19),border=ft.Border(bottom=ft.BorderSide(1,LINE)))
        self.intro=ft.Container(ft.Column([ft.Row([text("Small code. Big possibilities.",27,weight=ft.FontWeight.W_600,expand=True),]),
                                        text("Create a QR that feels like you. Fine-tune it. Make it yours.",12,MUTED)],spacing=6),
                           padding=ft.Padding.symmetric(horizontal=28,vertical=22))
        self.footer=ft.Container(ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE_ROUNDED,size=12,color=MUTED),
                                    text("Made on your device · works offline",10,MUTED),ft.Container(expand=True),
                                    text("QR Generator / 1.1.2",10,MUTED)],spacing=6),
                            padding=ft.Padding.symmetric(horizontal=28,vertical=12))
        self.mobile_nav=ft.Container(ft.Row([
            ft.TextButton("Customize",icon=ft.Icons.TUNE_ROUNDED,on_click=self.jump_customize,expand=True),
            ft.Button("Preview & export",icon=ft.Icons.QR_CODE_2_ROUNDED,on_click=self.jump_preview,
                      bgcolor=ACCENT,color=BG,expand=True)],spacing=10),
            padding=ft.Padding.symmetric(horizontal=16,vertical=9),visible=False,
            border=ft.Border(top=ft.BorderSide(1,LINE)))
        self.intro_host=ft.Container(self.intro)
        self.root=ft.Column([self.header,self.intro_host,self.workspace,self.mobile_nav,self.footer],spacing=0,expand=True)
        p.add(ft.SafeArea(self.root,minimum_padding=ft.Padding.only(bottom=8),expand=True))
        p.on_resize=self.on_resize
        self.layout()
        self.sync_visibility()
        self.schedule()

    def layout(self):
        width=self.page.width or 1280
        height=self.page.height or 900
        mobile=not (width>=900 or (width>=600 and width>height))
        compact=not mobile and height<600
        mode=(mobile,compact)
        if mode!=self.layout_mode:
            self.layout_mode=mode
            self.mobile=mobile
            self.header_hint.visible=not mobile and not compact
            self.mobile_nav.visible=mobile
            self.editor.scroll=None if mobile else ft.ScrollMode.AUTO
            self.editor.expand=not mobile
            self.header.padding=ft.Padding.symmetric(horizontal=28,vertical=10 if compact else 19)
            self.footer.visible=not compact
            self.preview_panel.padding=10 if compact else 24
            self.preview_panel.content.spacing=6 if compact else 13
            self.preview_panel.content.controls[1].visible=not compact
            self.preview_panel.content.controls[2].padding=ft.Padding.symmetric(vertical=0 if compact else 8)
            self.preview_surface.content.controls[1].padding=12 if compact else 24
            self.editor.controls=self.setting_cards.copy()
            if mobile:
                self.intro_host.content=None
                self.intro.padding=ft.Padding.symmetric(horizontal=12,vertical=16)
                self.workspace.content=ft.Column([self.intro,self.preview_panel,self.editor],scroll=ft.ScrollMode.AUTO,spacing=16,expand=True)
            else:
                self.intro_host.content=None if compact else self.intro
                self.intro.padding=ft.Padding.symmetric(horizontal=28,vertical=22)
                if compact:
                    self.intro.padding=ft.Padding.symmetric(horizontal=6,vertical=10)
                    self.editor.controls.insert(0,self.intro)
                self.workspace.content=ft.Row([self.preview_host,self.editor_host],spacing=14 if compact else 22,
                                               vertical_alignment=ft.CrossAxisAlignment.START,expand=True)
                self.preview_host.content=ft.Column([self.preview_panel],scroll=ft.ScrollMode.AUTO,expand=True)
            self.workspace.padding=ft.Padding.symmetric(horizontal=16 if mobile else 28)
        insets=self.page.media.view_padding
        safe_height=(insets.top or 0)+max(8,insets.bottom or 0)
        side=(min(220,max(112,height-safe_height-121),max(120,(width-80)*5/11-38)) if compact else
              min(384 if mobile else max(230,height-590),max(230,width-114 if mobile else (width-100)*5/11-48)))
        self.preview_surface.content.width=side
        self.preview_surface.content.height=side
        self.preview_surface.content.controls[0].width=side
        self.preview_surface.content.controls[0].height=side
        qrside=side-(24 if compact else 48)
        self.preview_image.width=qrside
        self.preview_image.height=qrside
        self.gpu_preview.resize(qrside)

    async def show_credits(self,e):
        self.page.show_dialog(ft.AlertDialog(title="Credits",bgcolor=PANEL,
            content=ft.Column([text("QR Generator",18,weight=ft.FontWeight.W_600),
                               text("Created by",12,MUTED),
                               text("Jirawat Pratuangtip",16),
                               ft.TextButton("github.com/Jirawat2105",url="https://github.com/Jirawat2105")],
                              tight=True,spacing=12),
            actions=[ft.TextButton("Close",on_click=lambda e:self.page.pop_dialog())]))

    async def complete_url_field(self,e):
        value=complete_url(self.controls["url"].value,commit=True)
        if value!=self.controls["url"].value:
            self.controls["url"].value=value
            self.controls["url"].selection=ft.TextSelection(base_offset=len(value),extent_offset=len(value))
            self.design=replace(self.design,url=value)
            self.schedule()

    async def jump_preview(self,e):
        if self.mobile:
            await self.workspace.content.scroll_to(offset=0,duration=300)

    async def jump_customize(self,e):
        if self.mobile:
            # The preview card has a stable intrinsic height, so jump to the editor
            # using its ScrollKey instead of estimating device-dependent pixels.
            await self.workspace.content.scroll_to(scroll_key="editor-start",duration=300)

    async def on_resize(self,e):
        self.layout()
        self.page.update()

    def sync_visibility(self):
        d=self.design
        self.controls["color_end"].visible=d.color_mode=="Gradient"
        self.controls["background_end"].visible=d.background_mode=="Gradient"
        self.bg_image_group.visible=d.background_mode=="Image"

    async def change(self,e):
        name=e.control.key
        value=e.control.value
        if name in ("logo_scale","logo_padding","angle","background_opacity","background_rounding","edge_blur","edge_opacity"):
            value=round(value)
        elif name=="resolution":
            try:
                value=int(value)
            except (ValueError,TypeError):
                self.design=replace(self.design,resolution=value)
                self.invalidate("Enter a whole-number resolution between 256 and 8192 px.")
                return
        elif name in ("color","color_end","background","background_end"):
            value=value.strip()
            if not value.startswith("#"):
                value="#"+value
        elif name=="url":
            value=complete_url(value)
            if value!=e.control.value:
                e.control.value=value
                e.control.selection=ft.TextSelection(base_offset=len(value),extent_offset=len(value))
            value=value.strip()
        self.design=replace(self.design,**{name:value})
        self.sync_visibility()
        self.schedule()

    def invalidate(self,message):
        self.generation+=1
        self.valid=False
        self.export_button.disabled=True
        self.zip_button.disabled=True
        self.error.value=message
        self.error.visible=True
        self.status.content.value="CHECK INPUT"
        # Prevent an old QR from looking like the current invalid destination.
        self.preview_image.opacity=.18
        self.page.update()

    def schedule(self):
        self.generation+=1
        if self.pending:
            self.pending.cancel()
        self.valid=False
        self.export_button.disabled=True
        self.zip_button.disabled=True
        self.error.visible=False
        self.status.content.value="UPDATING"
        self.preview_image.opacity=.5
        self.page.update()
        self.pending=self.page.run_task(self.update_preview,self.generation,self.design)

    async def update_preview(self,generation,design):
        try:
            await asyncio.sleep(.22)
            data,meta=await render_async(design,"PREVIEW",640)
            if generation!=self.generation:
                return
            self.gpu_preview.set_packet(data)
            self.preview_image.opacity=1
            self.last_data=data
            self.meta=meta
            self.valid=True
            self.status.content.value="LIVE PREVIEW"
            regular=f" (Regular: {meta['regular_modules']} × {meta['regular_modules']})" if meta['mode']=="Minimalist" else ""
            self.preview_meta.value=f"{meta['mode']} · {meta['modules']} × {meta['modules']} modules{regular}  ·  Error correction {meta['ecc']}"
            self.warning.value="\n".join(meta["warnings"])
            self.warning.visible=bool(meta["warnings"])
            self.error.visible=False
            self.export_button.disabled=self.exporting
            self.zip_button.disabled=self.exporting
            self.page.update()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if generation==self.generation:
                logging.exception("Preview failed")
                self.invalidate(str(exc))

    async def pick_asset(self,background=False):
        try:
            files=await self.picker.pick_files(dialog_title="Choose background" if background else "Choose logo",
                                               file_type=ft.FilePickerFileType.CUSTOM,
                                               allowed_extensions=["png","jpg","jpeg","webp"],with_data=True)
            if not files:
                return
            f=files[0]
            if f.size>16*1024*1024:
                raise ValueError("Choose an image smaller than 16 MB.")
            data=f.bytes if f.bytes is not None else Path(f.path).read_bytes() if f.path else None
            if not data:
                raise ValueError("The selected image could not be read.")
            data=await asyncio.to_thread(normalize_image,data)
            if background:
                self.design=replace(self.design,background_image=data,background_mode="Image")
                self.bg_name.value=f.name
            else:
                self.design=replace(self.design,logo=data)
                self.logo_name.value=f.name+" · original aspect ratio"
            self.schedule()
        except Exception as exc:
            self.notify(str(exc),error=True)

    async def pick_logo(self,e):
        await self.pick_asset()

    async def pick_background(self,e):
        await self.pick_asset(True)

    async def remove_logo(self,e):
        self.design=replace(self.design,logo=None)
        self.logo_name.value="PNG, JPG or WebP · original proportions"
        self.schedule()

    async def format_changed(self,e):
        self.format_help.value={"PNG":"PNG · transparent background supported",
                                 "SVG":"SVG · scalable QR vectors, embedded images",
                                 "PDF":"PDF · 300 dpi image, white transparency matte",
                                 "JPG":"JPG · high quality, white transparency matte"}[self.format.value]
        self.page.update()

    def notify(self,message,error=False):
        self.page.show_dialog(ft.SnackBar(text(message,12,"#FFA5A5" if error else BG),bgcolor="#382529" if error else ACCENT))

    def set_exporting(self,value):
        self.exporting=value
        self.export_button.disabled=value or not self.valid
        self.zip_button.disabled=value or not self.valid
        self.export_button.content="Preparing your file…" if value else "Export QR code"
        self.page.update()

    async def save(self,data,filename,extension):
        result=await self.picker.save_file(dialog_title="Export your QR",file_name=filename,
                                           file_type=ft.FilePickerFileType.CUSTOM,
                                           allowed_extensions=[extension],src_bytes=data)
        # Native pickers return None on cancel; web uses download without a path.
        if result or self.page.web:
            self.export_status.value=f"Saved {filename} · {len(data)/1024:.0f} KB"
            self.notify("Your QR is ready. Saved successfully.")
        else:
            self.export_status.value="Export cancelled. Your design is still here."
        self.page.update()

    async def export(self,e):
        if not self.valid or self.exporting:
            return
        self.set_exporting(True)
        snapshot=self.design
        fmt=self.format.value
        try:
            data,_=await render_async(snapshot,fmt)
            await self.save(data,f"qr-generator-{snapshot.resolution}.{fmt.lower()}",fmt.lower())
        except Exception as exc:
            logging.exception("Export failed")
            self.notify(f"Export failed: {exc}",error=True)
        finally:
            self.set_exporting(False)

    async def export_all(self,e):
        if not self.valid or self.exporting:
            return
        self.set_exporting(True)
        snapshot=self.design
        try:
            # Bounded worker pool runs two exports on separate CPU cores on Windows.
            outputs=await asyncio.gather(*(render_async(snapshot,fmt) for fmt in FORMATS))
            out=io.BytesIO()
            with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as bundle:
                for fmt,(data,_) in zip(FORMATS,outputs):
                    bundle.writestr(f"qr-generator-{snapshot.resolution}.{fmt.lower()}",data)
            await self.save(out.getvalue(),"qr-generator-all.zip","zip")
        except Exception as exc:
            logging.exception("Bundle export failed")
            self.notify(f"Export failed: {exc}",error=True)
        finally:
            self.set_exporting(False)

    async def reset(self,e):
        self.design=Design()
        for name,control in self.controls.items():
            if name.endswith("_readout"):
                field=name.removesuffix("_readout")
                suffix=" modules" if field=="logo_padding" else "°" if field=="angle" else "%"
                control.value=f"{getattr(self.design,field)}{suffix}"
            elif hasattr(self.design,name):
                value=getattr(self.design,name)
                control.value=str(value) if isinstance(control,ft.TextField) else value
        self.format.value="PNG"
        await self.format_changed(None)
        self.export_status.value=""
        self.logo_name.value="PNG, JPG or WebP · original proportions"
        self.bg_name.value="Choose a background image"
        self.sync_shapes()
        self.sync_visibility()
        self.schedule()


async def main(page: ft.Page):
    studio=Studio(page)
    studio.build()
