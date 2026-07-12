"""
Skeet - Moderner EXE-Launcher
==============================
Zeigt hinzugefuegte .exe-Programme als abgerundete Karten im 2-Spalten-Raster.

Benoetigte Pakete:
    pip install pillow pywin32
Optional (Drag & Drop von .exe-Dateien):
    pip install tkinterdnd2

Graustufen-Design, abgerundete Buttons, Starten-Button mit Gelb-Gruen-Verlauf,
dunkelgraue Titelleiste (nur Windows 11), hochaufgeloeste Icons direkt aus der EXE.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import json
import os
import sys
import subprocess
import hashlib
import ctypes

# ---------- Optional: Drag & Drop ----------
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_OK = True
except Exception:
    _DND_OK = False

# ---------- Icon-Extraktion (nur unter Windows via pywin32) ----------
try:
    import win32gui
    import win32ui
    import win32con
    import win32api
    _WIN32_OK = True
except Exception:
    _WIN32_OK = False

from PIL import Image, ImageTk, ImageDraw, ImageFont

BaseTk = TkinterDnD.Tk if _DND_OK else tk.Tk

# ---------- Reines Graustufen-Farbschema ----------
COLORS = {
    "bg":           "#202020",
    "topbar":       "#242424",
    "card":         "#2b2b2b",
    "card_hover":   "#363636",
    "shadow":       "#141414",
    "text":         "#f2f2f2",
    "text_muted":   "#9a9a9a",
    "btn_gray":     "#4a4a4a",
    "btn_gray_h":   "#5c5c5c",
    "btn_delete":   "#333333",
    "btn_delete_h": "#3f3f3f",
    "input_bg":     "#2f2f2f",
}

# Gelb -> Gruen Verlauf fuer den Starten-Button
GRADIENT_START = (233, 196, 41)     # Gelb
GRADIENT_END = (67, 160, 71)        # Gruen
GRADIENT_START_HOVER = (245, 212, 66)
GRADIENT_END_HOVER = (86, 184, 90)

# ---------- Speicherorte ----------
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "skeet_data.json")
ICON_DIR = os.path.join(APP_DIR, "icons")
os.makedirs(ICON_DIR, exist_ok=True)

ICON_EXTRACT_SIZE = 128   # Groesse, in der wir aus der EXE extrahieren (hohe Qualitaet)
ICON_DISPLAY_SIZE = 80    # Anzeigegroesse im Launcher


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"games": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- Icon-Handling ----------
def extract_icon(exe_path, size=ICON_EXTRACT_SIZE):
    """Liest ein moeglichst hochaufgeloestes Icon direkt aus der EXE.
    Nutzt PrivateExtractIconsW, um (falls vorhanden) die grosse Variante
    des eingebetteten Icons zu bekommen, statt nur die kleine System-Groesse."""
    if _WIN32_OK:
        try:
            from ctypes import wintypes
            shell32 = ctypes.windll.shell32
            hicons = (wintypes.HICON * 1)()
            icon_ids = (ctypes.c_uint * 1)()
            count = shell32.PrivateExtractIconsW(exe_path, 0, size, size, hicons, icon_ids, 1, 0)
            hicon = hicons[0] if count > 0 else 0

            if not hicon:
                large, small = win32gui.ExtractIconEx(exe_path, 0)
                for h in small:
                    win32gui.DestroyIcon(h)
                hicon = large[0] if large else 0

            if hicon:
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, size, size)
                hdc_mem = hdc.CreateCompatibleDC()
                hdc_mem.SelectObject(hbmp)
                hdc_mem.DrawIcon((0, 0), hicon)

                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer(
                    "RGBA", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                    bmpstr, "raw", "BGRA", 0, 1
                )
                win32gui.DestroyIcon(hicon)
                return img
        except Exception:
            pass
    return generate_placeholder(exe_path, size)


def generate_placeholder(name_or_path, size=ICON_EXTRACT_SIZE):
    name = os.path.splitext(os.path.basename(name_or_path))[0]
    letter = name[0].upper() if name else "?"
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=(95, 95, 95, 255))
    try:
        font = ImageFont.truetype("segoeui.ttf", int(size * 0.5))
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), letter, font=font, fill=(235, 235, 235, 255))
    return img


def cache_icon(exe_path):
    """Extrahiert das Icon einmalig in hoher Aufloesung und speichert es als PNG."""
    h = hashlib.md5(exe_path.encode("utf-8")).hexdigest()
    icon_filename = f"{h}_hq.png"
    icon_path = os.path.join(ICON_DIR, icon_filename)
    if not os.path.exists(icon_path):
        img = extract_icon(exe_path)
        img.save(icon_path)
    return icon_filename


def round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def make_rounded_image(width, height, radius, fill=None, gradient=None):
    """Erzeugt ein abgerundetes Rechteck (Vollfarbe oder horizontaler Verlauf) als RGBA-Bild."""
    if gradient:
        c1, c2 = gradient
        grad = Image.new("RGB", (width, height))
        gdraw = ImageDraw.Draw(grad)
        for x in range(width):
            t = x / max(width - 1, 1)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            gdraw.line([(x, 0), (x, height)], fill=(r, g, b))
        base = grad.convert("RGBA")
    else:
        base = Image.new("RGBA", (width, height), fill)

    mask = Image.new("L", (width, height), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=255)

    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def hex_to_rgba(hexcolor, alpha=255):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = int(hexcolor[0:2], 16), int(hexcolor[2:4], 16), int(hexcolor[4:6], 16)
    return (r, g, b, alpha)


def draw_play_icon(draw, cx, cy, size, color):
    h = size
    w = size * 0.85
    points = [
        (cx - w * 0.32, cy - h / 2),
        (cx - w * 0.32, cy + h / 2),
        (cx + w * 0.62, cy),
    ]
    draw.polygon(points, fill=color)


def draw_trash_icon(draw, cx, cy, size, color):
    w = size
    h = size * 1.05
    left, right = cx - w / 2, cx + w / 2
    top, bottom = cy - h / 2, cy + h / 2
    lw = max(2, int(size * 0.09))

    lid_h = h * 0.14
    lid_top = top
    lid_bottom = top + lid_h
    r_lid = max(1, min(lw, lid_h / 2, (right - left) / 2))
    draw.rounded_rectangle([left, lid_top, right, lid_bottom], radius=r_lid, fill=color)

    # Henkel als einfaches Rechteck (kein Radius noetig, ist ohnehin sehr klein)
    handle_w = w * 0.32
    handle_h = h * 0.16
    draw.rectangle([cx - handle_w / 2, top - handle_h, cx + handle_w / 2, lid_top + 1], outline=color, width=lw)

    body_top = lid_bottom + h * 0.06
    body_h = max(1, bottom - body_top)
    body_w = max(1, (right - w * 0.1) - (left + w * 0.1))
    r_body = max(1, min(lw * 1.5, body_h / 2, body_w / 2))
    draw.rounded_rectangle([left + w * 0.1, body_top, right - w * 0.1, bottom], radius=r_body, outline=color, width=lw)
    for frac in (0.32, 0.5, 0.68):
        x = left + w * frac
        draw.line([(x, body_top + h * 0.1), (x, bottom - h * 0.1)], fill=color, width=lw)
        draw.line([(x, body_top + h * 0.12), (x, bottom - h * 0.1)], fill=color, width=lw)


def draw_search_icon(draw, cx, cy, size, color):
    r = size * 0.34
    ccx, ccy = cx - size * 0.06, cy - size * 0.06
    lw = max(2, int(size * 0.11))
    draw.ellipse([ccx - r, ccy - r, ccx + r, ccy + r], outline=color, width=lw)
    hx1, hy1 = ccx + r * 0.72, ccy + r * 0.72
    hx2, hy2 = ccx + r * 1.55, ccy + r * 1.55
    draw.line([(hx1, hy1), (hx2, hy2)], fill=color, width=lw)


def make_button_image(width, height, radius, text, text_color, icon=None,
                       fill=None, gradient=None, font_size=12):
    """Rendert Hintergrund, Icon und Text in 4-facher Aufloesung und skaliert dann
    mit Kantenglaettung (LANCZOS) auf die Zielgroesse herunter - vermeidet Pixeligkeit."""
    scale = 4
    sw, sh, sr = width * scale, height * scale, radius * scale
    sfont = font_size * scale

    base = make_rounded_image(sw, sh, sr, fill=fill, gradient=gradient)
    draw = ImageDraw.Draw(base)
    try:
        font = ImageFont.truetype("segoeuib.ttf", sfont)
    except Exception:
        try:
            font = ImageFont.truetype("segoeui.ttf", sfont)
        except Exception:
            font = ImageFont.load_default()

    color = hex_to_rgba(text_color) if isinstance(text_color, str) else text_color

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    icon_size = sh * 0.4
    gap = sh * 0.22
    total_w = (icon_size + gap + text_w) if icon else text_w
    start_x = (sw - total_w) / 2

    if icon == "play":
        draw_play_icon(draw, start_x + icon_size / 2, sh / 2, icon_size, color)
        text_x = start_x + icon_size + gap
    elif icon == "trash":
        draw_trash_icon(draw, start_x + icon_size / 2, sh / 2, icon_size, color)
        text_x = start_x + icon_size + gap
    else:
        text_x = start_x

    text_y = (sh - text_h) / 2 - bbox[1]
    draw.text((text_x, text_y), text, font=font, fill=color)

    return base.resize((width, height), Image.LANCZOS)


class RoundedButton(tk.Canvas):
    """Ein Button mit abgerundeten Ecken, selbst gezeichnetem Icon, Vollfarbe oder Farbverlauf, inkl. Hover."""

    def __init__(self, parent, text, command, width=110, height=36, radius=14,
                 bg_color="#2b2b2b", fill=None, hover_fill=None,
                 gradient=None, hover_gradient=None,
                 text_color="#ffffff", font_size=12, icon=None):
        super().__init__(parent, width=width, height=height, bg=bg_color,
                          highlightthickness=0, cursor="hand2")
        self.command = command

        img_normal = make_button_image(width, height, radius, text, text_color, icon,
                                        fill=fill, gradient=gradient, font_size=font_size)
        img_hover = make_button_image(width, height, radius, text, text_color, icon,
                                       fill=hover_fill or fill, gradient=hover_gradient or gradient,
                                       font_size=font_size)
        self._img_normal = ImageTk.PhotoImage(img_normal)
        self._img_hover = ImageTk.PhotoImage(img_hover)

        self.image_id = self.create_image(0, 0, image=self._img_normal, anchor="nw")

        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self.itemconfig(self.image_id, image=self._img_hover))
        self.bind("<Leave>", lambda e: self.itemconfig(self.image_id, image=self._img_normal))

    def set_bg(self, color):
        self.configure(bg=color)


class SearchBar(tk.Canvas):
    """Abgerundetes Suchfeld mit Lupen-Icon und Platzhaltertext."""

    def __init__(self, parent, width=260, height=40, radius=18,
                 bg_color="#242424", fill="#333333", placeholder="Suchen...",
                 on_change=None):
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0)
        self.on_change = on_change
        self.placeholder = placeholder
        self._placeholder_active = True

        scale = 4
        sw, sh = width * scale, height * scale
        bg_img = make_rounded_image(sw, sh, radius * scale, fill=fill)
        draw = ImageDraw.Draw(bg_img)
        draw_search_icon(draw, sw * (20 / width), sh / 2, sh * 0.5, hex_to_rgba(COLORS["text_muted"]))
        bg_img = bg_img.resize((width, height), Image.LANCZOS)
        self._img = ImageTk.PhotoImage(bg_img)
        self.create_image(0, 0, image=self._img, anchor="nw")

        self.entry = tk.Entry(self, bg=fill, fg=COLORS["text_muted"], insertbackground=COLORS["text"],
                               bd=0, font=("Segoe UI", 10), highlightthickness=0)
        self.entry.insert(0, placeholder)
        self.create_window(42, height / 2, window=self.entry, anchor="w", width=width - 56)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<KeyRelease>", self._on_key)

    def _on_focus_in(self, event=None):
        if self._placeholder_active:
            self.entry.delete(0, "end")
            self.entry.configure(fg=COLORS["text"])
            self._placeholder_active = False

    def _on_focus_out(self, event=None):
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.configure(fg=COLORS["text_muted"])
            self._placeholder_active = True

    def _on_key(self, event=None):
        if self.on_change:
            self.on_change()

    def get_query(self):
        return "" if self._placeholder_active else self.entry.get().strip()


# ---------- Einzelne App-Karte ----------
class AppCard(tk.Frame):
    RADIUS = 24

    def __init__(self, parent, game, launcher):
        super().__init__(parent, bg=COLORS["bg"])
        self.game = game
        self.launcher = launcher
        self.hovered = False
        self._shadow_offset = 4

        self.canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=COLORS["card"])
        self._build_content()

        # Kartenhoehe an den tatsaechlichen Inhalt anpassen (verhindert abgeschnittene Buttons)
        self.inner.update_idletasks()
        self._content_height = self.inner.winfo_reqheight()
        self.card_height = self._content_height + 14 * 2 + 12
        self.canvas.configure(height=self.card_height)

        self.inner_window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")

        self.canvas.bind("<Configure>", self._redraw)
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Double-Button-1>", lambda e: self.launcher.start_game(self.game))
        self.canvas.bind("<Button-3>", self._show_context_menu)

    def _build_content(self):
        icon_path = os.path.join(ICON_DIR, self.game.get("icon", ""))
        try:
            pil_img = Image.open(icon_path).resize((ICON_DISPLAY_SIZE, ICON_DISPLAY_SIZE), Image.LANCZOS)
        except Exception:
            pil_img = generate_placeholder(self.game["name"], ICON_DISPLAY_SIZE)
        self.icon_img = ImageTk.PhotoImage(pil_img)

        icon_label = tk.Label(self.inner, image=self.icon_img, bg=COLORS["card"])
        icon_label.pack(pady=(20, 8))

        name_label = tk.Label(self.inner, text=self.game["name"], bg=COLORS["card"], fg=COLORS["text"],
                               font=("Segoe UI", 11, "bold"), wraplength=220, justify="center")
        name_label.pack(pady=(0, 14))

        btn_row = tk.Frame(self.inner, bg=COLORS["card"])
        btn_row.pack(pady=(0, 16))

        self.start_btn = RoundedButton(
            btn_row, text="Starten", command=lambda: self.launcher.start_game(self.game),
            width=124, height=40, radius=18, bg_color=COLORS["card"],
            gradient=(GRADIENT_START, GRADIENT_END),
            hover_gradient=(GRADIENT_START_HOVER, GRADIENT_END_HOVER),
            text_color="#1a1a1a", icon="play"
        )
        self.start_btn.pack(side="left", padx=6)

        self.delete_btn = RoundedButton(
            btn_row, text="Löschen", command=lambda: self.launcher.delete_game(self.game),
            width=118, height=40, radius=18, bg_color=COLORS["card"],
            fill=COLORS["btn_delete"], hover_fill=COLORS["btn_delete_h"],
            text_color=COLORS["text_muted"], icon="trash"
        )
        self.delete_btn.pack(side="left", padx=6)

        for w in (icon_label, name_label, btn_row):
            w.bind("<Double-Button-1>", lambda e: self.launcher.start_game(self.game))
            w.bind("<Button-3>", self._show_context_menu)

    def _redraw(self, event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        self.canvas.delete("shape")
        off = self._shadow_offset
        r = self.RADIUS

        self.canvas.create_polygon(
            round_rect_points(4, 4 + off, w - 4, h - 4 + off, r),
            smooth=True, fill=COLORS["shadow"], outline="", tags="shape"
        )
        fill = COLORS["card_hover"] if self.hovered else COLORS["card"]
        self.canvas.create_polygon(
            round_rect_points(4, 4, w - 4, h - 4, r),
            smooth=True, fill=fill, outline="", tags="shape"
        )
        self.canvas.tag_lower("shape")

        pad = 14
        self.canvas.coords(self.inner_window, pad, pad)
        self.canvas.itemconfig(self.inner_window, width=w - pad * 2, height=self._content_height)

    def _on_enter(self, event=None):
        self.hovered = True
        bg = COLORS["card_hover"]
        self._recolor(self.inner, bg)
        self.start_btn.set_bg(bg)
        self.delete_btn.set_bg(bg)
        self._animate_shadow(9)

    def _on_leave(self, event=None):
        self.hovered = False
        bg = COLORS["card"]
        self._recolor(self.inner, bg)
        self.start_btn.set_bg(bg)
        self.delete_btn.set_bg(bg)
        self._animate_shadow(4)

    def _recolor(self, widget, bg):
        try:
            if widget.winfo_class() in ("Label", "Frame"):
                widget.configure(bg=bg)
        except tk.TclError:
            pass
        for c in widget.winfo_children():
            self._recolor(c, bg)

    def _animate_shadow(self, target):
        def step():
            if self._shadow_offset == target:
                self._redraw()
                return
            self._shadow_offset += 1 if target > self._shadow_offset else -1
            self._redraw()
            self.after(10, step)
        step()

    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=COLORS["card"], fg=COLORS["text"],
                        activebackground=COLORS["btn_gray"], activeforeground=COLORS["text"], bd=0)
        menu.add_command(label="Starten", command=lambda: self.launcher.start_game(self.game))
        menu.add_command(label="Entfernen", command=lambda: self.launcher.delete_game(self.game))
        menu.add_separator()
        menu.add_command(label="Speicherort öffnen", command=lambda: self.launcher.open_location(self.game))
        menu.add_command(label="Eigenschaften", command=lambda: self.launcher.show_properties(self.game))
        menu.tk_popup(event.x_root, event.y_root)


# ---------- Hauptfenster ----------
class Skeet(BaseTk):
    def __init__(self):
        super().__init__()
        self.title("Skeet")
        self.geometry("1000x700")
        self.minsize(650, 500)
        self.configure(bg=COLORS["bg"])

        self.data = load_data()
        self.cards = []

        self._build_ui()
        self.render_grid()
        self.after(50, self._set_titlebar_color)

        if _DND_OK:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    # ---------- Windows-11 Titelleiste einfaerben ----------
    def _set_titlebar_color(self):
        if sys.platform != "win32":
            return
        try:
            self.update()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

            def to_colorref(hexcolor):
                hexcolor = hexcolor.lstrip("#")
                r, g, b = int(hexcolor[0:2], 16), int(hexcolor[2:4], 16), int(hexcolor[4:6], 16)
                return r | (g << 8) | (b << 16)

            DWMWA_CAPTION_COLOR = 35
            DWMWA_TEXT_COLOR = 36
            caption = ctypes.c_int(to_colorref(COLORS["topbar"]))
            text_c = ctypes.c_int(to_colorref(COLORS["text"]))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(caption), ctypes.sizeof(caption))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(text_c), ctypes.sizeof(text_c))
        except Exception:
            pass  # Funktioniert nur ab Windows 11 - unter Windows 10 einfach ignorieren

    # ---------- Aufbau ----------
    def _build_ui(self):
        topbar = tk.Frame(self, bg=COLORS["topbar"], height=64)
        topbar.pack(side="top", fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="Skeet", bg=COLORS["topbar"], fg=COLORS["text"],
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=20)

        add_btn = RoundedButton(
            topbar, text="+ App hinzufügen", command=self.add_game,
            width=170, height=40, radius=18, bg_color=COLORS["topbar"],
            fill=COLORS["btn_gray"], hover_fill=COLORS["btn_gray_h"],
            text_color=COLORS["text"]
        )
        add_btn.pack(side="right", padx=20)

        self.search_bar = SearchBar(
            topbar, width=260, height=40, radius=18,
            bg_color=COLORS["topbar"], fill=COLORS["input_bg"],
            placeholder="Suchen...", on_change=self.render_grid
        )
        self.search_bar.pack(side="right", padx=10)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True)

        footer = tk.Frame(self, bg=COLORS["bg"], height=36)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Label(footer, text="Skeet v1.0.0  •  Made with ♥", bg=COLORS["bg"], fg=COLORS["text_muted"],
                 font=("Segoe UI", 9)).pack(pady=8)

        self.canvas = tk.Canvas(body, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.grid_frame.grid_columnconfigure(0, weight=1, uniform="col")
        self.grid_frame.grid_columnconfigure(1, weight=1, uniform="col")

        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resize_grid_frame)

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _resize_grid_frame(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ---------- Rendering ----------
    def render_grid(self):
        for c in self.grid_frame.winfo_children():
            c.destroy()
        self.cards = []

        query = self.search_bar.get_query().lower()
        games = [g for g in self.data["games"] if query in g["name"].lower()] if query else self.data["games"]

        if not games:
            text = "Keine Apps gefunden." if query else "Noch keine Apps hinzugefügt."
            tk.Label(self.grid_frame, text=text, bg=COLORS["bg"], fg=COLORS["text_muted"],
                     font=("Segoe UI", 11)).grid(row=0, column=0, columnspan=2, pady=40)
            return

        for i, game in enumerate(games):
            card = AppCard(self.grid_frame, game, self)
            card.grid(row=i // 2, column=i % 2, padx=14, pady=14, sticky="nsew")
            self.cards.append(card)

    # ---------- App-Verwaltung ----------
    def add_game(self):
        path = filedialog.askopenfilename(title="EXE-Datei auswählen", filetypes=[("Programme", "*.exe")])
        if not path:
            return
        self._add_game_from_path(path)

    def _add_game_from_path(self, path):
        if not path.lower().endswith(".exe"):
            messagebox.showwarning("Ungültige Datei", "Bitte wähle eine .exe-Datei aus.")
            return
        if any(g["path"] == path for g in self.data["games"]):
            messagebox.showinfo("Bereits vorhanden", "Diese App ist bereits im Launcher.")
            return
        name = os.path.splitext(os.path.basename(path))[0]
        icon_filename = cache_icon(path)
        self.data["games"].append({"name": name, "path": path, "icon": icon_filename})
        save_data(self.data)
        self.render_grid()

    def _on_drop(self, event):
        paths = self.tk.splitlist(event.data)
        for p in paths:
            self._add_game_from_path(p)

    def start_game(self, game):
        try:
            subprocess.Popen(game["path"])
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte die App nicht starten:\n{e}")

    def delete_game(self, game):
        if not messagebox.askyesno(
            "Entfernen bestätigen",
            f"'{game['name']}' aus dem Launcher entfernen?\n(Die Datei selbst wird nicht gelöscht.)"
        ):
            return
        self.data["games"] = [g for g in self.data["games"] if g["path"] != game["path"]]
        save_data(self.data)
        self.render_grid()

    def open_location(self, game):
        try:
            subprocess.Popen(f'explorer /select,"{game["path"]}"')
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte den Ordner nicht öffnen:\n{e}")

    def show_properties(self, game):
        try:
            os.startfile(game["path"], "properties")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Eigenschaften nicht öffnen:\n{e}")


if __name__ == "__main__":
    app = Skeet()
    app.mainloop()
