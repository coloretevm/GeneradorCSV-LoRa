"""Device-first, guided desktop interface for Device Manager."""

from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageOps

from device_manager_flow import PRODUCTS, VARIANTS, WizardSession, actions_for, firmware_for, manuals_for
from device_manager_icons import InterfaceIcons
from device_manager_preview import render_pdf
from device_manager_ui_text import TEXT, translate


BG = ("#edf3f9", "#24364b")
CARD = ("#ffffff", "#304760")
INK = ("#142c43", "#f2f7fd")
MUTED = ("#526b82", "#c5d5e4")
BLUE = ("#23669f", "#82b4eb")
HOVER = ("#195587", "#a2ccf7")
SOFT = ("#e7f0f9", "#3c5875")
LINE = ("#c9d8e7", "#57738f")
GREEN = ("#168465", "#38bb94")
RED = ("#b33c43", "#ffb4b7")
HEADING = "Bahnschrift"
BODY = "Segoe UI Variable Text"


class ProductImages:
    # Normalized windows onto the product photographs in the approved artwork.
    BOXES = {
        "RTU": (65, 302, 247, 519), "LORACONT": (586, 301, 799, 521),
        "Gateway": (1055, 322, 1280, 514), "I-TIC": (68, 552, 298, 764),
        "TIC12": (582, 548, 800, 771), "Istantaneo": (1058, 548, 1303, 771),
    }

    def __init__(self, resource):
        self.source = Image.open(resource(os.path.join("assets", "guided", "products_reference.png"))).convert("RGB")
        self.cache = {}

    def get(self, product, size=(152, 152)):
        key = product, size
        if key not in self.cache:
            sx, sy = self.source.width / 1586, self.source.height / 993
            box = tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(self.BOXES[product]))
            crop = self.source.crop(box)
            image = Image.new("RGB", size, "white")
            crop = ImageOps.contain(crop, (size[0] - 12, size[1] - 12), Image.Resampling.LANCZOS)
            image.paste(crop, ((size[0] - crop.width) // 2, (size[1] - crop.height) // 2))
            self.cache[key] = ctk.CTkImage(image, image, size=size)
        return self.cache[key]


class PdfWindow(ctk.CTkToplevel):
    def __init__(self, owner, path, title):
        super().__init__(owner.root)
        self.owner, self.path, self.index, self.total = owner, str(path), 0, 1
        self.title(title)
        self.geometry(f"{min(940, owner.available_width-40)}x{min(800, owner.available_height-60)}")
        self.minsize(min(680, owner.available_width-50), min(560, owner.available_height-70))
        self.configure(fg_color=BG)
        bar = ctk.CTkFrame(self, fg_color=CARD)
        bar.pack(fill="x", padx=12, pady=12)
        owner.button(bar, owner.tr("close_document"), self.destroy, secondary=True,
                     image=owner.icons.get("back", 16), compound="left", width=160).pack(side="left", padx=6)
        self.previous = owner.button(bar, "<", lambda: self.turn(-1), width=44)
        self.previous.pack(side="left", padx=6, pady=8)
        self.counter = owner.label(bar, "", size=13)
        self.counter.pack(side="left", padx=10)
        self.following = owner.button(bar, ">", lambda: self.turn(1), width=44)
        self.following.pack(side="left", padx=6)
        owner.button(bar, owner.tr("save"), lambda: owner.save_asset(self.path), width=150).pack(side="right", padx=8)
        owner.button(bar, owner.tr("open"), lambda: owner.open_path(self.path), width=90, secondary=True).pack(side="right", padx=4)
        self.scroller = ctk.CTkScrollableFrame(self, fg_color=BG, label_text="")
        self.scroller.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.image_label = ctk.CTkLabel(self.scroller, text="")
        self.image_label.pack(pady=8)
        self.show_page()
        self.after(200, self.lift)

    def show_page(self):
        try:
            image, self.total = render_pdf(self.path, self.index, width=820)
            self.page_image = ctk.CTkImage(image, image, size=image.size)
            self.image_label.configure(image=self.page_image, text="")
            self.counter.configure(text=self.owner.tr("document_page").format(index=self.index + 1, total=self.total))
            self.previous.configure(state="normal" if self.index else "disabled")
            self.following.configure(state="normal" if self.index + 1 < self.total else "disabled")
            self.scroller._parent_canvas.yview_moveto(0)
        except Exception as exc:
            self.image_label.configure(image=None, text=str(exc))

    def turn(self, offset):
        if 0 <= self.index + offset < self.total:
            self.index += offset
            self.show_page()


class WizardView(ctk.CTkFrame):
    def __init__(self, owner, session):
        super().__init__(owner.body, fg_color="transparent")
        self.owner, self.session, self.index = owner, session, 0
        self.preview_path = None
        self.temp = tempfile.TemporaryDirectory(prefix="DeviceManager_preview_")
        self.error_text = tk.StringVar(master=self, value="")
        self.nav = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16, border_width=1, border_color=LINE)
        self.nav.pack(side="bottom", fill="x", pady=(12, 0))
        self.back_button = owner.button(self.nav, owner.tr("back"), self.back, secondary=True, width=130)
        self.back_button.pack(side="left", padx=14, pady=12)
        self.step_label = owner.label(self.nav, "", size=12, color=MUTED)
        self.step_label.pack(side="left", padx=12)
        self.next_button = owner.button(self.nav, owner.tr("next"), self.next, width=165)
        self.next_button.pack(side="right", padx=14)
        self.error = ctk.CTkLabel(self, textvariable=self.error_text, text_color=RED, anchor="w", wraplength=900)
        self.error.pack(side="bottom", fill="x", pady=(8, 0))
        self.panel = ctk.CTkScrollableFrame(self, fg_color=CARD, corner_radius=18, label_text="",
                                            border_width=1, border_color=LINE)
        self.panel.pack(fill="both", expand=True)
        self.refresh()

    def field_label(self, key):
        return self.owner.tr(key) if key in TEXT else self.owner.clean(self.owner.api.t(key))

    def refresh(self):
        for child in self.panel.winfo_children():
            child.destroy()
        self.error_text.set("")
        steps = self.session.steps()
        self.index = min(self.index, len(steps))
        review = self.index == len(steps)
        self.owner.set_progress(3 if review else 2)
        self.owner.update_breadcrumb(self.session.product, self.session.variant, self.session.action)
        self.back_button.configure(text=self.owner.tr("back"))
        self.next_button.configure(text=self.owner.tr("generate") if review else self.owner.tr("next"), state="normal")
        self.step_label.configure(text=self.owner.tr("step_count").format(index=self.index + 1, total=len(steps) + 1))
        if review:
            self.review()
        else:
            step = steps[self.index]
            if step.key.startswith("gateway:"):
                title = self.owner.tr("gateway_step").format(index=int(step.key.split(":")[1]) + 1,
                                                            total=self.session.quantity_var.get())
            else:
                title = self.owner.tr(step.key + "_step")
            self.owner.label(self.panel, title, size=26, bold=True).pack(anchor="w", padx=22, pady=(22, 6))
            help_key = "serial_help" if step.key in ("serial", "labels_data") else "step_help"
            self.owner.label(self.panel, self.owner.tr(help_key), size=13, color=MUTED, wrap=850).pack(anchor="w", padx=22, pady=(0, 16))
            if self.session.product == "I-TIC" and step.key == "labels_data":
                self.owner.label(self.panel, "Collegamento Solenoide Bistabile 12v DC\nCavo Rosso - V1_C    |    Cavo Nero - V1_O",
                                 size=13, color=MUTED).pack(anchor="w", padx=22, pady=(0, 12))
            for field in step.fields:
                self.add_field(field)
        self.panel._parent_canvas.yview_moveto(0)

    def add_field(self, field):
        row = ctk.CTkFrame(self.panel, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=7)
        self.owner.label(row, self.field_label(field.label), size=13, bold=True).pack(anchor="w", pady=(0, 5))
        variable = self.session.field_var(field)
        if field.kind == "choice":
            widget = ctk.CTkComboBox(row, variable=variable, values=list(field.choices), state="readonly",
                                   height=40, width=240, fg_color=SOFT, border_color=LINE, text_color=INK,
                                   button_color=BLUE, button_hover_color=HOVER,
                                   dropdown_fg_color=CARD, dropdown_text_color=INK)
            widget.pack(anchor="w")
        else:
            line = ctk.CTkFrame(row, fg_color="transparent")
            line.pack(fill="x")
            widget = ctk.CTkEntry(line, textvariable=variable, height=40, corner_radius=10,
                                 fg_color=SOFT, text_color=INK, border_color=LINE, font=(BODY, 14))
            widget.pack(side="left", fill="x", expand=True)
            if field.kind == "readonly":
                widget.configure(state="readonly")
            if field.kind in ("pdf", "csv", "csv_input", "folder"):
                self.owner.button(line, self.owner.tr("browse"), lambda f=field: self.browse(f),
                                  width=110, secondary=True).pack(side="left", padx=(10, 0))
        if field.attr == "tic_from" or field.attr in ("serial_start", "p_ser_start"):
            self.owner.label(row, self.owner.tr("serial_help"), size=11, color=MUTED, wrap=800).pack(anchor="w", pady=(4, 0))

    def browse(self, field):
        var = self.session.field_var(field)
        current = str(var.get()).strip()
        if field.kind == "folder":
            path = filedialog.askdirectory(parent=self, initialdir=current if os.path.isdir(current) else self.owner.api._desktop_dir())
        elif field.kind == "csv_input":
            path = filedialog.askopenfilename(parent=self, filetypes=[("CSV", "*.csv")])
        else:
            extension = ".pdf" if field.kind == "pdf" else ".csv"
            path = filedialog.asksaveasfilename(parent=self, defaultextension=extension,
                initialdir=os.path.dirname(current) or self.owner.api._desktop_dir(), initialfile=os.path.basename(current),
                filetypes=[(extension[1:].upper(), "*" + extension)])
        if path:
            var.set(path)
            tool = self.session.tool
            if hasattr(tool, "_pdf_output_auto"):
                tool._pdf_output_auto = False

    def report(self, exc):
        key = str(exc)
        if key == "serial_not_ready":
            self.error_text.set(self.owner.tr(key))
        elif key in TEXT or key.startswith(("lbl_", "gw_")):
            self.error_text.set(self.owner.tr("invalid_field").format(field=self.field_label(key)))
        else:
            self.error_text.set(key)

    def back(self):
        if self.index:
            self.index -= 1
            self.refresh()
        else:
            self.owner.show_actions(self.session.product, self.session.variant)

    def next(self):
        steps = self.session.steps()
        if self.index == len(steps):
            self.generate()
            return
        try:
            self.session.validate_step(steps[self.index])
            if self.session.needs_serial and not self.session.serial_ready:
                raise RuntimeError("serial_not_ready")
            self.index += 1
            self.refresh()
        except Exception as exc:
            self.report(exc)

    def review(self):
        self.owner.label(self.panel, self.owner.tr("ready_title"), size=26, bold=True).pack(anchor="w", padx=22, pady=(22, 12))
        try:
            self.session.prepare()
            summary = f"{self.session.product}  /  {self.owner.variant_text(self.session.variant)}\n"
            summary += f"{self.owner.tr('count')}: {self.session.count()}\n"
            if self.session.needs_serial:
                summary += f"{self.owner.tr('serials')}: {self.session.serial_range()}\n"
            summary += f"\n{self.owner.tr('output')}:\n" + "\n".join(self.session.output_paths())
            self.owner.label(self.panel, summary, size=13, wrap=880, color=MUTED).pack(fill="x", padx=22, pady=(0, 15))
            self.preview_path, text = self.session.preview(self.temp.name)
            if self.preview_path:
                self.owner.label(self.panel, self.owner.tr("preview_hint"), size=12, color=MUTED).pack(anchor="w", padx=22)
                self.owner.button(self.panel, self.owner.tr("open_preview"),
                                  lambda: self.owner.open_pdf(self.preview_path, self.owner.tr("preview")),
                                  secondary=True).pack(anchor="w", padx=22, pady=10)
                image, _ = render_pdf(self.preview_path, width=520)
                self.preview_image = ctk.CTkImage(image, image, size=image.size)
                ctk.CTkLabel(self.panel, text="", image=self.preview_image).pack(padx=22, pady=(0, 20))
            else:
                box = ctk.CTkTextbox(self.panel, height=350, fg_color=SOFT, text_color=INK, font=("Consolas", 13))
                box.pack(fill="x", padx=22, pady=(0, 20))
                box.insert("1.0", text)
                box.configure(state="disabled")
        except Exception as exc:
            self.next_button.configure(state="disabled")
            self.report(exc)

    def generate(self):
        try:
            self.session.validate_all()
            if self.session.needs_serial and not self.session.serial_ready:
                raise RuntimeError("serial_not_ready")
            paths = self.session.output_paths()
            if any(os.path.exists(path) for path in paths):
                if not messagebox.askyesno(self.owner.tr("review"), self.owner.tr("overwrite"), parent=self):
                    return
            self.next_button.configure(state="disabled", text=self.owner.tr("working"))
            self.update_idletasks()
            serial_range = self.session.serial_range()
            result = self.session.generate()
            if result:
                self.owner.show_result(self.session, result, serial_range)
            else:
                self.next_button.configure(state="normal", text=self.owner.tr("generate"))
        except Exception as exc:
            self.next_button.configure(state="normal", text=self.owner.tr("generate"))
            self.report(exc)


class GuidedApp:
    def __init__(self, root, api):
        self.root, self.api = root, api
        self.sessions, self.wizards, self.utility_cache = {}, {}, {}
        self.current = None
        self.active_route = ("home",)
        self.registry = None
        self.sync_running = False
        self.closed = False
        self.events = queue.Queue()
        self.prefs_path = Path(api._runtime_dir()) / "guided_ui_settings.json"
        preferences = {}
        try:
            preferences = json.loads(self.prefs_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        api._cur_lang[0] = preferences.get("language", "it") if preferences.get("language", "it") in ("it", "es", "en") else "it"
        self.dark = preferences.get("theme") == "dark"
        ctk.set_appearance_mode("dark" if self.dark else "light")
        root.title("Device Manager - TECNIDRO")
        root.configure(fg_color=BG)
        scale = root._get_window_scaling()
        self.available_width = int(root.winfo_screenwidth() / scale)
        self.available_height = int(root.winfo_screenheight() / scale)
        self.compact = self.available_height < 780
        width, height = min(int(self.available_width * .94), 1440), min(self.available_height-60, 1000)
        root.geometry(f"{width}x{height}+{(self.available_width-width)//2}+{(self.available_height-height)//2}")
        root.minsize(min(980, self.available_width-30), min(680, self.available_height-60))
        self.window_icon = tk.PhotoImage(file=api._resource("tecnidro_app_icon.png"))
        root.iconphoto(True, self.window_icon)
        self.images = ProductImages(api._resource)
        self.icons = InterfaceIcons()
        self.shell = ctk.CTkFrame(root, fg_color="transparent")
        self.shell.pack(fill="both", expand=True, padx=18, pady=12)
        header = ctk.CTkFrame(self.shell, fg_color=CARD, corner_radius=18, border_width=1, border_color=LINE)
        header.pack(fill="x", pady=(0, 12))
        light, dark, lw, lh = api._make_logo_images(display_h=44 if self.compact else 56)
        self.logo = ctk.CTkImage(light, dark, size=(lw, lh))
        ctk.CTkLabel(header, image=self.logo, text="").pack(side="left", padx=(22, 18), pady=10)
        names = ctk.CTkFrame(header, fg_color="transparent")
        names.pack(side="left", fill="y", pady=10)
        self.label(names, "Device Manager", size=25 if self.compact else 29, bold=True).pack(anchor="w")
        self.label(names, "TECNIDRO SRL", size=12, color=MUTED).pack(anchor="w")
        self.language_var = tk.StringVar(master=root, value={"it": "Italiano", "es": "Español", "en": "English"}[api._cur_lang[0]])
        ctk.CTkComboBox(header, variable=self.language_var, values=["Italiano", "Español", "English"], state="readonly",
                        command=self.change_language, width=132, height=36, fg_color=SOFT, text_color=INK,
                        border_color=LINE, button_color=BLUE, dropdown_fg_color=CARD, dropdown_text_color=INK).pack(side="right", padx=(8, 18))
        self.theme_button = self.button(header, self.tr("theme"), self.toggle_theme, secondary=True, width=82)
        self.theme_button.pack(side="right", padx=5)
        self.home_button = self.button(header, self.tr("home"), self.show_home, secondary=True, width=85)
        self.home_button.pack(side="right", padx=5)
        self.previous_menu_button = self.button(header, self.tr("previous_menu"), self.go_back, secondary=True,
                                                image=self.icons.get("back", 16), compound="left", width=160)
        self.previous_menu_button.pack(side="right", padx=5)
        self.breadcrumb = self.label(self.shell, "", size=12, color=MUTED)
        self.breadcrumb.pack(anchor="w", padx=4, pady=(0, 8))
        progress = ctk.CTkFrame(self.shell, fg_color="transparent")
        progress.pack(fill="x", pady=(0, 10))
        self.progress_labels = []
        for i, key in enumerate(("device", "operation", "data", "review")):
            progress.grid_columnconfigure(i, weight=1)
            label = self.label(progress, f"{i+1}  {self.tr(key)}", size=14, bold=True)
            label.grid(row=0, column=i, sticky="ew", padx=4, ipady=6)
            label.configure(corner_radius=12)
            self.progress_labels.append(label)
        footer = ctk.CTkFrame(self.shell, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.connection = self.label(footer, self.tr("serial_loading"), size=11, color=MUTED)
        self.connection.pack(side="left")
        self.retry_button = self.button(footer, self.tr("retry"), self.start_sync, secondary=True, width=84, height=28)
        self.retry_button.pack(side="left", padx=10)
        self.label(footer, f"v{api.APP_VERSION}     by Manuel Rodriguez", size=11, color=MUTED).pack(side="right")
        self.body = ctk.CTkFrame(self.shell, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.hidden_forms = ctk.CTkFrame(root)
        self._transient = None
        api._lang_cbs.append(self.language_refresh)
        api._register_serial_refresh_callback(self.on_registry_change)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self.poll_events)
        self.show_home()
        self.root.after(250, self.start_sync)
        settings = api._load_update_settings()
        if settings.get("auto_check") and settings.get("manifest_url"):
            self.root.after(1800, lambda: api.check_for_updates(root, interactive=False))

    def tr(self, key):
        return translate(key, self.api._cur_lang[0])

    @staticmethod
    def clean(value):
        value = str(value)
        for _ in range(2):
            try:
                fixed = value.encode("latin1").decode("utf-8")
                if fixed == value:
                    break
                value = fixed
            except (UnicodeError, ValueError):
                break
        return value

    def label(self, parent, text, size=14, bold=False, color=INK, wrap=0):
        return ctk.CTkLabel(parent, text=text, text_color=color, anchor="w", justify="left", wraplength=wrap, height=size+6,
                            font=ctk.CTkFont(family=HEADING if bold else BODY, size=size, weight="bold" if bold else "normal"))

    def button(self, parent, text, command, secondary=False, **kwargs):
        return ctk.CTkButton(parent, text=text, command=command, height=kwargs.pop("height", 40),
            corner_radius=10, fg_color=SOFT if secondary else BLUE, hover_color=LINE if secondary else HOVER,
            text_color=INK if secondary else ("white", "#132b42"), font=(BODY, 13, "bold"), **kwargs)

    def set_progress(self, active):
        self.previous_menu_button.configure(state="disabled" if self.active_route[0] == "home" else "normal")
        for i, (label, key) in enumerate(zip(self.progress_labels, ("device", "operation", "data", "review"))):
            label.configure(text=f"{i+1}  {self.tr(key)}", fg_color=BLUE if i == active else SOFT,
                            text_color=("white", "#132b42") if i == active else MUTED)

    def variant_text(self, variant):
        return self.tr(variant) if variant else ""

    def go_back(self):
        route = self.active_route
        if route[0] == "variants":
            self.show_home()
        elif route[0] == "actions":
            if route[1] in VARIANTS:
                self.show_variants(route[1])
            else:
                self.show_home()
        elif route[0] == "wizard":
            self.show_actions(route[1], route[2])
        elif route[0] in ("firmware", "documents") and route[1]:
            self.show_actions(route[1], route[2])
        elif route[0] == "shutdown":
            self.show_actions("Gateway", "")
        elif route[0] == "result":
            self.show_actions(route[1].product, route[1].variant)
        else:
            self.show_home()

    def update_breadcrumb(self, product="", variant="", action=""):
        parts = [self.tr("home")]
        if product:
            parts.append(product)
        if variant:
            parts.append(self.variant_text(variant))
        if action:
            parts.append(self.tr(action))
        self.breadcrumb.configure(text="  /  ".join(parts))

    def display(self, frame):
        if self.current is not None:
            self.current.pack_forget()
        if self._transient is not None and self._transient is not frame:
            self._transient.destroy()
            self._transient = None
        frame.pack(fill="both", expand=True)
        self.current = frame

    def new_page(self, title, hint=""):
        page = ctk.CTkFrame(self.body, fg_color="transparent")
        self.display(page)
        self._transient = page
        self.label(page, title, size=26 if self.compact else 30, bold=True).pack(anchor="w", padx=4, pady=(4, 4))
        if hint:
            self.label(page, hint, size=13, color=MUTED, wrap=1100).pack(anchor="w", padx=4, pady=(0, 12))
        return page

    def show_home(self):
        self.active_route = ("home",)
        self.set_progress(0)
        self.update_breadcrumb()
        page = self.new_page(self.tr("home_title"), self.tr("home_hint"))
        utilities = ctk.CTkFrame(page, fg_color=CARD, corner_radius=16, border_width=1, border_color=LINE)
        utilities.pack(side="bottom", fill="x", pady=(12, 0))
        self.utility_buttons = {}
        for key in ("firmwares", "manuals", "terminals", "settings"):
            utilities.grid_columnconfigure(("firmwares", "manuals", "terminals", "settings").index(key), weight=1)
            button = self.button(utilities, self.tr(key), lambda k=key: self.show_utility(k), secondary=True, height=38,
                                 image=self.icons.get(key), compound="left")
            button.configure(fg_color="transparent")
            button.grid(row=0, column=("firmwares", "manuals", "terminals", "settings").index(key), sticky="ew", padx=8, pady=7)
            self.utility_buttons[key] = button
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", label_text="")
        scroll.pack(fill="both", expand=True)
        cards = []
        self.product_buttons = {}
        for product in PRODUCTS:
            card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=18, border_width=1, border_color=LINE, height=140 if self.compact else 190)
            photo_size = 116 if self.compact else 152
            photo = ctk.CTkLabel(card, text="", image=self.images.get(product, (photo_size, photo_size)), fg_color="white", corner_radius=14)
            photo.pack(side="left", padx=(12, 8), pady=12 if self.compact else 16)
            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12 if self.compact else 20)
            name = self.label(info, product, size=21 if self.compact else 23, bold=True)
            name.pack(anchor="w")
            description = self.tr("rtu_desc" if product in ("RTU", "LORACONT") else "gw_desc" if product == "Gateway" else "labels_desc")
            desc = self.label(info, description, size=12 if self.compact else 13, color=MUTED, wrap=150)
            desc.pack(anchor="w", pady=(5, 5))
            button = self.button(info, self.tr("open_device"), lambda p=product: self.choose_product(p), secondary=True,
                                 image=self.icons.get("enter", 15), compound="right", width=146, height=30)
            button.pack(anchor="w")
            self.product_buttons[product] = button
            for widget in (card, photo, name, desc):
                widget.bind("<Button-1>", lambda event, p=product: self.choose_product(p))
            cards.append(card)
        state = {"columns": 0}
        def resize(event):
            if not scroll.winfo_exists():
                return
            columns = 3 if event.width / scroll._get_widget_scaling() >= 1000 else 2
            if columns == state["columns"]:
                return
            state["columns"] = columns
            for i in range(3):
                scroll.grid_columnconfigure(i, weight=1 if i < columns else 0, uniform="products" if i < columns else "")
            for i, card in enumerate(cards):
                card.grid(row=i // columns, column=i % columns, sticky="nsew", padx=6, pady=6)
        scroll.bind("<Configure>", resize, add="+")
        self.root.after_idle(lambda: resize(type("Size", (), {"width": max(800, self.body.winfo_width()-12)})()))

    def choose_product(self, product):
        if product not in PRODUCTS:
            return
        if product in VARIANTS:
            self.show_variants(product)
        else:
            self.show_actions(product, "")

    def show_variants(self, product):
        self.active_route = ("variants", product)
        self.set_progress(0)
        self.update_breadcrumb(product)
        page = self.new_page(product + " - " + self.tr("variant_title"), self.tr("variant_hint"))
        grid = ctk.CTkScrollableFrame(page, fg_color="transparent", label_text="")
        grid.pack(fill="both", expand=True)
        for i, variant in enumerate(VARIANTS[product]):
            grid.grid_columnconfigure(i % 2, weight=1, uniform="variant")
            card = ctk.CTkFrame(grid, fg_color=CARD, corner_radius=18, border_width=1, border_color=LINE)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=8, pady=8)
            self.label(card, self.variant_text(variant), size=24, bold=True).pack(anchor="w", padx=24, pady=(24, 10))
            if variant == "nbiot":
                self.label(card, self.tr("nbiot_hint"), size=13, color=MUTED, wrap=450).pack(anchor="w", padx=24, pady=(0, 12))
            self.button(card, self.tr("next"), lambda v=variant: self.show_actions(product, v)).pack(anchor="w", padx=24, pady=(0, 24))

    def show_actions(self, product, variant):
        self.active_route = ("actions", product, variant)
        self.set_progress(1)
        self.update_breadcrumb(product, variant)
        page = self.new_page(product + (" / " + self.variant_text(variant) if variant else ""), self.tr("action_title"))
        self.label(page, self.tr("action_hint"), color=MUTED, size=13).pack(anchor="w", padx=4, pady=(0, 10))
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", label_text="")
        scroll.pack(fill="both", expand=True)
        for i, action in enumerate(actions_for(product, variant)):
            scroll.grid_columnconfigure(i % 2, weight=1, uniform="action")
            card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=16, border_width=1, border_color=LINE)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=8, pady=8)
            self.label(card, self.tr(action), size=22, bold=True, wrap=500).pack(anchor="w", padx=22, pady=(18, 6))
            self.label(card, self.tr(action + "_hint"), size=13, color=MUTED, wrap=480).pack(anchor="w", padx=22, pady=(0, 12))
            self.button(card, self.tr("next"), lambda a=action: self.start_action(product, variant, a)).pack(anchor="w", padx=22, pady=(0, 18))
        if product in VARIANTS:
            self.button(page, self.tr("back"), lambda: self.show_variants(product), secondary=True).pack(anchor="w", pady=(10, 0))

    def start_action(self, product, variant, action):
        if action not in actions_for(product, variant):
            raise ValueError("Unsupported action")
        if action == "firmware":
            self.show_firmware(product, variant)
        elif action in ("manual", "guide"):
            self.show_documents(product, variant, action)
        elif action == "shutdown":
            self.show_shutdown()
        else:
            key = (product, variant, action)
            if key in self.sessions and self.sessions[key].result:
                self.dispose_session(key)
            if key not in self.sessions:
                session = WizardSession(self.api, self.hidden_forms, product, variant, action)
                if self.registry is not None:
                    session.sync_serial(self.registry)
                self.sessions[key] = session
                self.wizards[key] = WizardView(self, session)
            self.active_route = ("wizard",) + key
            self.display(self.wizards[key])
            self.wizards[key].refresh()

    def show_firmware(self, product=None, variant=""):
        self.active_route = ("firmware", product, variant)
        self.set_progress(1)
        self.update_breadcrumb(product or "", variant, "firmware")
        page = self.new_page((product + " / " if product else "") + self.tr("firmware"), self.tr("firmware_help"))
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", label_text="")
        scroll.pack(fill="both", expand=True)
        self.pic_buttons = []
        self.firmware_status = self.label(page, "", size=12, color=GREEN)
        self.firmware_status.pack(anchor="w", padx=5, pady=6)
        if product:
            sections = [(product, firmware_for(self.api, product, variant), 0)]
        else:
            sections = [
                ("RTU", firmware_for(self.api, "RTU"), 0),
                ("LORACONT", firmware_for(self.api, "LORACONT"), 0),
                ("RTU NBIoT", firmware_for(self.api, "RTU", "nbiot"), 0),
                ("TIC12", firmware_for(self.api, "TIC12"), 1),
                ("I-TIC", firmware_for(self.api, "I-TIC", "rev6") + firmware_for(self.api, "I-TIC", "rev4"), 1),
                ("Istantaneo", firmware_for(self.api, "Istantaneo", "new") + firmware_for(self.api, "Istantaneo", "old"), 1),
            ]
        self.firmware_section_names = [name for name, _, _ in sections]
        columns = [ctk.CTkFrame(scroll, fg_color="transparent") for _ in range(2)]
        self.firmware_row_buttons = []
        narrow = product is None
        for name, items, column in sections:
            card = ctk.CTkFrame(columns[column], fg_color=CARD, corner_radius=12, border_width=1, border_color=LINE)
            card.pack(fill="x", padx=4, pady=(0, 9))
            title = ctk.CTkFrame(card, fg_color=SOFT, corner_radius=9)
            title.pack(fill="x", padx=5, pady=(5, 3))
            self.label(title, name, size=13, bold=True).pack(anchor="w", padx=10, pady=5)
            for index, item in enumerate(items):
                self.add_firmware_row(card, item, narrow)
                if index + 1 < len(items):
                    ctk.CTkFrame(card, height=1, fg_color=LINE).pack(fill="x", padx=10)
        layout = {"count": 0}
        def resize(event):
            if not scroll.winfo_exists():
                return
            count = 2 if narrow and event.width / scroll._get_widget_scaling() >= 980 else 1
            if count == layout["count"]:
                return
            layout["count"] = count
            for i in range(2):
                scroll.grid_columnconfigure(i, weight=1 if i < count else 0,
                                            uniform="firmware_columns" if i < count else "")
                columns[i].grid(row=0 if count == 2 else i, column=i if count == 2 else 0,
                                sticky="new", padx=3)
            if product:
                columns[1].grid_remove()
        scroll.bind("<Configure>", resize, add="+")
        self.root.after_idle(lambda: resize(type("Size", (), {"width": max(800, self.body.winfo_width()-12)})()))
        if product:
            self.button(page, self.tr("back"), lambda: self.show_actions(product, variant), secondary=True).pack(anchor="w", pady=8)

    def add_firmware_row(self, parent, item, narrow):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=9, pady=4)
        row.grid_columnconfigure(0, weight=1)
        name = self.clean(self.api.t(item["label_key"]))
        name = name.replace(" - " + item["pic"], "")
        many = len(item["firmwares"]) > 2
        self.label(row, name, size=11 if narrow else 13, wrap=150 if narrow else 340).grid(
            row=0, column=0, sticky="w", padx=(1, 6))
        pic = self.button(row, item["pic"], None, width=133 if narrow else 160, height=29)
        pic.configure(fg_color="#223145", hover_color="#324a63", text_color="white", font=(BODY, 10 if narrow else 12, "bold"),
                      command=lambda b=pic, value=item["pic"]: self.copy_pic(value, b))
        pic.grid(row=0, column=2, sticky="e", padx=(5, 0))
        self.pic_buttons.append(pic)
        buttons = ctk.CTkFrame(row, fg_color="transparent")
        if many:
            buttons.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        else:
            buttons.grid(row=0, column=1, sticky="e")
        for index, (label, filename) in enumerate(item["firmwares"]):
            text = label.replace("versionhe", "versione")
            if narrow and "/NOROLL " in text:
                text = text.replace("/NOROLL ", "/NOROLL\n")
            column = index % 3 if many else index
            buttons.grid_columnconfigure(column, weight=1 if many else 0)
            button = self.button(buttons, text,
                lambda f=filename: self.save_asset(self.api._resource(os.path.join("fw", f))),
                width=96 if narrow else 150, height=34 if "\n" in text else 29)
            button.configure(font=(BODY, 10 if narrow else 12, "bold"))
            button.grid(row=index // 3 if many else 0, column=column, sticky="ew", padx=2, pady=2)
            self.firmware_row_buttons.append((item["label_key"], filename, button))

    def copy_pic(self, value, button):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        for current in self.pic_buttons:
            current.configure(fg_color="#223145", hover_color="#324a63")
        button.configure(fg_color="#1f8f5f", hover_color="#18724c")
        self.firmware_status.configure(text=self.tr("copied") + ": " + value)

    def show_documents(self, product=None, variant="", action="manual"):
        self.active_route = ("documents", product, variant, action)
        self.set_progress(1)
        self.update_breadcrumb(product or "", variant, action)
        title = self.tr("guide") if action == "guide" else self.tr("documents")
        page = self.new_page((product + " / " if product else "") + title)
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent", label_text="")
        scroll.pack(fill="both", expand=True)
        groups = [(product, manuals_for(self.api, product))] if product else [
            (self.clean(self.api.t(key)), paths) for key, paths in self.api.ManualsTab.MANUAL_GROUPS]
        for group, paths in groups:
            self.label(scroll, group, size=20, bold=True).pack(anchor="w", padx=12, pady=(12, 8))
            for relative in paths:
                card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=14, border_width=1, border_color=LINE)
                card.pack(fill="x", padx=6, pady=6)
                source = self.api._resource(relative)
                name = os.path.basename(relative)
                sheet_key = self.api.ManualsTab.SHEET_LABEL_KEYS.get(relative)
                text = self.clean(self.api.t(sheet_key)) if sheet_key else name
                self.label(card, text, size=14, bold=True, wrap=850).pack(anchor="w", padx=18, pady=(14, 8))
                actions = ctk.CTkFrame(card, fg_color="transparent")
                actions.pack(anchor="w", padx=18, pady=(0, 14))
                self.button(actions, self.tr("open"), lambda p=source, n=name: self.open_pdf(p, n), width=100).pack(side="left")
                self.button(actions, self.tr("save"), lambda p=source: self.save_asset(p), secondary=True).pack(side="left", padx=10)
        if product:
            self.button(page, self.tr("back"), lambda: self.show_actions(product, variant), secondary=True).pack(anchor="w", pady=8)

    def show_shutdown(self):
        self.active_route = ("shutdown",)
        self.set_progress(1)
        self.update_breadcrumb("Gateway", "", "shutdown")
        page = self.new_page(self.tr("shutdown"), self.tr("shutdown_help"))
        box = ctk.CTkTextbox(page, height=130, fg_color=CARD, text_color=INK, border_width=1, border_color=LINE, font=("Consolas", 15))
        box.pack(fill="x", pady=12)
        box.insert("1.0", self.api.GatewayTab.X4S_LTE_SHUTDOWN_CMD)
        box.configure(state="disabled")
        status = self.label(page, "", size=13, color=GREEN)
        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.api.GatewayTab.X4S_LTE_SHUTDOWN_CMD)
            status.configure(text=self.tr("copied"))
        self.button(page, self.tr("copy"), copy).pack(anchor="w", pady=12)
        status.pack(anchor="w")
        self.button(page, self.tr("back"), lambda: self.show_actions("Gateway", ""), secondary=True).pack(anchor="w", pady=20)

    def show_utility(self, key):
        if key == "firmwares":
            self.show_firmware()
        elif key == "manuals":
            self.show_documents()
        elif key == "terminals":
            self.show_terminals()
        else:
            self.show_settings()

    def show_terminals(self):
        self.active_route = ("terminals",)
        self.set_progress(1)
        self.update_breadcrumb(action="terminals")
        page = self.new_page(self.tr("terminals"), self.tr("terminal_hint"))
        for name, filename in (("Hyperterminal", self.api.SerialTab.PACKAGE_FILE),
                               ("Terminal Antonio - RTU Bluetooth / LORACONT", self.api.SerialTab.TERMINAL_ANTONIO_FILE)):
            self.label(page, name, size=20, bold=True).pack(anchor="w", pady=(20, 8))
            self.button(page, self.tr("save"), lambda f=filename: self.save_asset(self.api._resource(f))).pack(anchor="w")

    def show_settings(self):
        self.active_route = ("settings",)
        self.set_progress(1)
        self.update_breadcrumb(action="settings")
        if "settings" not in self.utility_cache:
            page = ctk.CTkFrame(self.body, fg_color="transparent")
            tabs = ctk.CTkTabview(page, fg_color=CARD)
            tabs.pack(fill="both", expand=True)
            for name, tab in (("settings_language", self.api.LangTab), ("settings_serial", self.api.SerialTab)):
                target = tabs.add(self.tr(name))
                tool = tab(target)
                tool.pack(fill="both", expand=True)
                self.api._apply_premium_theme(tool)
            self.utility_cache["settings"] = page
        self.display(self.utility_cache["settings"])

    def show_result(self, session, result, serial_range):
        self.active_route = ("result", session, result, serial_range)
        self.set_progress(3)
        self.update_breadcrumb(session.product, session.variant, session.action)
        page = self.new_page(self.tr("done"), self.tr("done_hint") if session.needs_serial else self.tr("done_files"))
        self.label(page, f"{session.product}   /   {self.variant_text(session.variant)}\n{self.tr('count')}: {result['count']}",
                   size=22, bold=True).pack(anchor="w", pady=16)
        if serial_range:
            self.label(page, self.tr("serials") + ": " + serial_range, size=16, color=GREEN).pack(anchor="w", pady=8)
        for path in result["files"]:
            self.label(page, str(path), size=13, color=MUTED, wrap=950).pack(anchor="w", pady=(12, 4))
            row = ctk.CTkFrame(page, fg_color="transparent")
            row.pack(anchor="w", pady=4)
            self.button(row, self.tr("open"), lambda p=path: self.open_path(p), width=110).pack(side="left")
            self.button(row, self.tr("open_folder"), lambda p=path: self.open_path(p if os.path.isdir(p) else os.path.dirname(p)),
                        secondary=True).pack(side="left", padx=8)
        self.button(page, self.tr("another"), lambda: self.show_actions(session.product, session.variant)).pack(anchor="w", pady=24)

    def open_pdf(self, path, title):
        if not os.path.isfile(path):
            messagebox.showerror("Device Manager", self.tr("missing_file").format(name=os.path.basename(path)), parent=self.root)
            return
        PdfWindow(self, path, title)

    def open_path(self, path):
        try:
            os.startfile(os.path.abspath(path))
        except OSError as exc:
            messagebox.showerror("Device Manager", str(exc), parent=self.root)

    def save_asset(self, source):
        if not os.path.isfile(source):
            messagebox.showerror("Device Manager", self.tr("missing_file").format(name=os.path.basename(source)), parent=self.root)
            return
        suffix = Path(source).suffix
        target = filedialog.asksaveasfilename(parent=self.root, initialfile=os.path.basename(source), defaultextension=suffix,
                                             filetypes=[(suffix.lstrip(".").upper(), "*" + suffix)])
        if not target:
            return
        try:
            if os.path.normcase(os.path.abspath(source)) != os.path.normcase(os.path.abspath(target)):
                shutil.copyfile(source, target)
            messagebox.showinfo("Device Manager", self.tr("saved"), parent=self.root)
        except OSError as exc:
            messagebox.showerror("Device Manager", str(exc), parent=self.root)

    def start_sync(self):
        if self.sync_running or self.closed:
            return
        self.sync_running = True
        self.connection.configure(text=self.tr("serial_loading"), text_color=MUTED)
        def work():
            try:
                registry = self.api._serial_registry_fetch(self.api._load_serial_settings())
                self.events.put(("registry", registry))
            except Exception as exc:
                self.events.put(("sync_error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def poll_events(self):
        if self.closed:
            return
        try:
            while True:
                event, data = self.events.get_nowait()
                self.sync_running = False
                if event == "registry":
                    self.registry = data
                    self.connection.configure(text=self.tr("serial_ok"), text_color=GREEN)
                    self.retry_button.pack_forget()
                    for session in self.sessions.values():
                        session.sync_serial(data)
                else:
                    self.connection.configure(text=self.tr("serial_error"), text_color=RED)
                    self.retry_button.pack(side="left", padx=10)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    def on_registry_change(self):
        registry = self.api._serial_registry_cache
        if registry is not None:
            self.events.put(("registry", registry))

    def save_preferences(self):
        self.dark = ctk.get_appearance_mode().lower() == "dark"
        try:
            self.prefs_path.write_text(json.dumps({"language": self.api._cur_lang[0], "theme": "dark" if self.dark else "light"}), encoding="utf-8")
        except OSError:
            pass

    def toggle_theme(self):
        self.dark = ctk.get_appearance_mode().lower() != "dark"
        ctk.set_appearance_mode("dark" if self.dark else "light")
        self.save_preferences()

    def change_language(self, value):
        self.api.set_lang({"Italiano": "it", "Español": "es", "English": "en"}.get(value, "it"))
        self.save_preferences()

    def language_refresh(self):
        self.language_var.set({"it": "Italiano", "es": "Español", "en": "English"}[self.api._cur_lang[0]])
        self.home_button.configure(text=self.tr("home"))
        self.previous_menu_button.configure(text=self.tr("previous_menu"))
        self.theme_button.configure(text=self.tr("theme"))
        self.retry_button.configure(text=self.tr("retry"))
        route = self.active_route
        if route[0] == "home":
            self.show_home()
        elif route[0] == "variants":
            self.show_variants(route[1])
        elif route[0] == "actions":
            self.show_actions(*route[1:])
        elif route[0] == "wizard":
            self.wizards[route[1:]].refresh()
        elif route[0] == "firmware":
            self.show_firmware(*route[1:])
        elif route[0] == "documents":
            self.show_documents(*route[1:])
        elif route[0] == "shutdown":
            self.show_shutdown()
        elif route[0] == "terminals":
            self.show_terminals()
        elif route[0] == "result":
            self.show_result(*route[1:])

    def dispose_session(self, key):
        session = self.sessions.pop(key)
        view = self.wizards.pop(key)
        for callbacks in (self.api._lang_cbs, self.api._serial_refresh_callbacks, self.api._rtu_deveui_refresh_callbacks):
            callbacks[:] = [callback for callback in callbacks if getattr(callback, "__self__", None) is not session.tool]
        session.tool.destroy()
        try:
            view.temp.cleanup()
        except OSError:
            pass
        view.destroy()

    def close(self):
        self.closed = True
        self.save_preferences()
        for key in list(self.sessions):
            self.dispose_session(key)
        self.root.destroy()
