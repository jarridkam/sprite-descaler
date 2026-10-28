"""Sprite Descaler GUI with built-in pixel editor. Run: python gui.py [image]"""
import queue
import sys
import threading
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk

import descale as D
import pixelize as PX
import bgremove as BG
import advise as AD
import gba as GBA
import metrics as MT

UNDO_LIMIT = 100
SRC_PREVIEW = 220


GBA_W, GBA_H = 240, 160
GBA_BGS = {"Black": (0, 0, 0), "White": (255, 255, 255), "Grass": (104, 176, 72),
           "Sky": (120, 184, 232), "Cave": (96, 88, 96), "Sand": (216, 200, 144)}


class FineSlider(ttk.Frame):
    """Slider + number box. Arrow keys nudge by step (Shift = 10x), double-click resets."""

    def __init__(self, parent, text, lo, hi, val, step, cmd):
        super().__init__(parent)
        self.lo, self.hi, self.step, self.default, self.cmd = lo, hi, step, val, cmd
        self.dec = max(0, -int(np.floor(np.log10(step)))) if step < 1 else 0
        self.var = tk.DoubleVar(value=val)
        self.sv = tk.StringVar(value=self._fmt(val))
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text=text).pack(side="left")
        self.sp = ttk.Spinbox(top, from_=lo, to=hi, increment=step, width=7, textvariable=self.sv,
                              command=self._from_entry)
        self.sp.pack(side="right")
        self.sp.bind("<Return>", lambda e: self._from_entry())
        self.sp.bind("<FocusOut>", lambda e: self._from_entry())
        self.sc = ttk.Scale(self, from_=lo, to=hi, variable=self.var, command=self._from_scale)
        self.sc.pack(fill="x")
        self.sc.bind("<Double-Button-1>", lambda e: self.set(self.default, notify=True))
        self.sc.bind("<Button-1>", lambda e: self.sc.focus_set(), add="+")
        for key, d in (("Left", -1), ("Right", 1), ("Down", -1), ("Up", 1)):
            self.sc.bind(f"<{key}>", lambda e, d=d: self._nudge(d * self.step))
            self.sc.bind(f"<Shift-{key}>", lambda e, d=d: self._nudge(d * self.step * 10))

    def _fmt(self, v):
        return f"{v:.{self.dec}f}"

    def get(self):
        return float(self.var.get())

    def set(self, v, notify=False):
        v = round(min(self.hi, max(self.lo, round(v / self.step) * self.step)), 10)
        self.var.set(v)
        self.sv.set(self._fmt(v))
        if notify:
            self.cmd()

    def _from_scale(self, v):
        q = round(float(v) / self.step) * self.step
        if abs(q - self.get()) > 1e-12:
            self.var.set(q)
        txt = self._fmt(q)
        if self.sv.get() != txt:
            self.sv.set(txt)
            self.cmd()

    def _from_entry(self):
        try:
            v = float(self.sv.get())
        except ValueError:
            self.sv.set(self._fmt(self.get()))
            return
        if abs(min(self.hi, max(self.lo, v)) - self.get()) > 1e-12:
            self.set(v, notify=True)
        else:
            self.sv.set(self._fmt(self.get()))

    def _nudge(self, d):
        self.set(self.get() + d, notify=True)
        return "break"


class GbaPreview(tk.Toplevel):
    """Live 240x160 GBA-screen preview of the current sprite."""

    def __init__(self, app):
        super().__init__(app)
        self.title("GBA preview (240x160)")
        self.app = app
        self.scale = tk.IntVar(value=3)
        self.bg = tk.StringVar(value="Grass")
        self.c15 = tk.BooleanVar(value=True)
        self.lcd = tk.BooleanVar(value=False)
        self.pos = None  # sprite top-left in GBA pixels
        self._shape = None
        self.drag = None

        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        ttk.Label(bar, text="Scale").pack(side="left")
        ttk.Spinbox(bar, from_=1, to=4, textvariable=self.scale, width=3, command=self.refresh).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="BG").pack(side="left")
        cb = ttk.Combobox(bar, textvariable=self.bg, values=list(GBA_BGS), state="readonly", width=7)
        cb.pack(side="left", padx=(2, 8))
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Checkbutton(bar, text="15-bit color", variable=self.c15, command=self.refresh).pack(side="left")
        ttk.Checkbutton(bar, text="LCD grid", variable=self.lcd, command=self.refresh).pack(side="left", padx=6)
        ttk.Button(bar, text="Center", command=self.center).pack(side="left")
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#000000", cursor="fleur")
        self.canvas.pack(padx=4, pady=4)
        self.canvas.bind("<Button-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.refresh()

    def center(self):
        self.pos = None
        self.refresh()

    def _sprite(self):
        p = self.app.pix
        if p is None:
            return None
        px = p.copy()
        if self.c15.get():  # GBA stores 5 bits per channel
            c = px[..., :3]
            px[..., :3] = (c & 0xF8) | (c >> 5)
        return Image.fromarray(px, "RGBA")

    def refresh(self):
        sp = self._sprite()
        s = max(1, min(4, int(self.scale.get())))
        frame = Image.new("RGBA", (GBA_W, GBA_H), GBA_BGS[self.bg.get()] + (255,))
        if sp is not None:
            if self.pos is None or self._shape != sp.size:
                self.pos = ((GBA_W - sp.width) // 2, (GBA_H - sp.height) // 2)
                self._shape = sp.size
            self._paste(frame, sp)
        if self.c15.get():
            a = np.array(frame)
            a[..., :3] = (a[..., :3] & 0xF8) | (a[..., :3] >> 5)
            frame = Image.fromarray(a, "RGBA")
        big = frame.resize((GBA_W * s, GBA_H * s), Image.NEAREST)
        if self.lcd.get() and s >= 2:
            a = np.array(big)
            a[::s, :, :3] = (a[::s, :, :3] * 0.8).astype(np.uint8)
            a[:, ::s, :3] = (a[:, ::s, :3] * 0.8).astype(np.uint8)
            big = Image.fromarray(a, "RGBA")
        self._tk = ImageTk.PhotoImage(big)
        self.canvas.config(width=GBA_W * s, height=GBA_H * s)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._tk, anchor="nw")

    def _paste(self, frame, sp):
        x, y = self.pos
        # clip so partially off-screen sprites still render
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        layer.paste(sp, (x, y))
        frame.alpha_composite(layer)

    def on_down(self, e):
        s = max(1, int(self.scale.get()))
        self.drag = (e.x // s, e.y // s)

    def on_drag(self, e):
        if self.pos is None or self.drag is None:
            return
        s = max(1, int(self.scale.get()))
        x, y = e.x // s, e.y // s
        self.pos = (self.pos[0] + x - self.drag[0], self.pos[1] + y - self.drag[1])
        self.drag = (x, y)
        self.refresh()


class App(tk.Tk):
    def __init__(self, path=None):
        super().__init__()
        self.title("Sprite Descaler")
        self.src = None
        self.path = None
        self.state_ = None
        self.pix = None            # (h,w,4) uint8, the editable result
        self.dirty = False         # user edited pixels since last render
        self.undo, self.redo = [], []
        self.color = (0, 0, 0, 255)
        self.tool = tk.StringVar(value="pencil")
        self.zoom = 8
        self.grid_on = tk.BooleanVar(value=True)
        self.last_cell = None
        self.q = queue.Queue()
        self.gba = None

        self._build()
        self.show_tabs()
        self.after(100, self._poll)
        self.bind("<Control-z>", lambda e: self.do_undo())
        self.bind("<Control-y>", lambda e: self.do_redo())
        self.bind("<Control-Z>", lambda e: self.do_redo())
        if path:
            self.after(200, lambda: self.load(path))

    # ---------- layout ----------
    def _build(self):
        self.f = {}
        self._after_ids = {}
        self.mode = "descale"
        self.px_src = None
        self.bg_on = tk.BooleanVar(value=False)
        self.bg_mode = tk.StringVar(value="edges")
        self.bg_color = None
        self.picking = False
        self._clean_cache = None
        self.px_state = None       # prepared pixelizer state
        self.px_key = None
        self.px_busy = False
        self.px_pending = False
        self.outer = tk.BooleanVar(value=False)
        self.tidy = tk.BooleanVar(value=True)
        self.gen3 = tk.BooleanVar(value=True)
        self._chk_id = None
        self.c15 = tk.BooleanVar(value=False)
        self.sil = tk.BooleanVar(value=True)

        side = ttk.Frame(self, padding=8)
        side.grid(row=0, column=0, sticky="ns")
        ttk.Button(side, text="Open sprite (descale)…", command=self.open).pack(fill="x")
        ttk.Button(side, text="Open artwork (pixelize)…", command=self.pixelize_open).pack(fill="x", pady=2)

        top = ttk.Frame(side)
        top.pack(fill="x", pady=(6, 0))
        ttk.Label(top, text="Size").pack(side="left")
        self.size = tk.StringVar(value="64x64")
        cb = ttk.Combobox(top, textvariable=self.size, values=list(D.SIZES), state="readonly", width=7)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_change("size"))
        ttk.Label(top, text="Colors").pack(side="left", padx=(6, 0))
        self.colors = tk.IntVar(value=15)
        ttk.Spinbox(top, from_=2, to=64, textvariable=self.colors, width=4).pack(side="left", padx=2)
        ttk.Label(top, text="Margin").pack(side="left", padx=(6, 0))
        self.margin = tk.IntVar(value=2)
        ttk.Spinbox(top, from_=0, to=8, textvariable=self.margin, width=3,
                    command=lambda: self.on_change("size")).pack(side="left", padx=2)

        nb = ttk.Notebook(side)
        nb.pack(fill="x", pady=6)
        t_desc, t_ref, t_grid, t_pix, t_pcol, t_bg = (ttk.Frame(nb, padding=4) for _ in range(6))
        nb.add(t_desc, text="Descale")
        nb.add(t_ref, text="Refine")
        nb.add(t_grid, text="Grid")
        nb.add(t_pix, text="Pixelize")
        nb.add(t_pcol, text="Pix color")
        nb.add(t_bg, text="Background")
        self.nb = nb
        self.tabs_for = {"descale": [t_desc, t_ref, t_grid, t_bg], "pixelize": [t_pix, t_pcol, t_bg]}
        self.all_tabs = [(t_desc, "Descale"), (t_ref, "Refine"), (t_grid, "Grid"), (t_pix, "Pixelize"),
                         (t_pcol, "Pix color"), (t_bg, "Background")]

        # key, label, lo, hi, default, step, kind
        spec = {
            t_desc: [("detail", "Detail protect", 0, 1, 0.15, 0.005, "render"),
                     ("outline", "Outline boost", 1, 3, 1.15, 0.01, "render"),
                     ("thin", "Thin-line protect", 1, 4, 1.8, 0.01, "render"),
                     ("light", "Shading (re-analyzes)", 1, 4, D.LIGHT_WEIGHT, 0.05, "none")],
            t_ref: [("merge", "Color merge threshold (dE)", 0, 30, 0.0, 0.1, "render"),
                    ("speckle", "Speckle cleanup (0=off)", 0, 1, 0.6, 0.01, "render"),
                    ("smooth", "Neighbor smoothing", 0, 1, 0.0, 0.01, "render"),
                    ("alpha_cut", "Edge coverage cutoff", 0.05, 0.95, 0.5, 0.01, "render"),
                    ("sat", "Saturation", 0, 2, 1.0, 0.01, "render"),
                    ("contrast", "Contrast", 0.5, 1.5, 1.0, 0.01, "render")],
            t_grid: [("gpx", "Cell width tweak (px)", -2, 2, 0.0, 0.01, "grid"),
                     ("gpy", "Cell height tweak (px)", -2, 2, 0.0, 0.01, "grid"),
                     ("gox", "Grid X offset (cells)", -0.5, 0.5, 0.0, 0.005, "grid"),
                     ("goy", "Grid Y offset (cells)", -0.5, 0.5, 0.0, 0.005, "grid")],
            t_pix: [("p_line", "Line amount", 0, 1, 0.4, 0.01, "pix"),
                    ("p_labs", "Line max brightness", 20, 255, 95, 1, "pix"),
                    ("p_lrel", "Line contrast needed", 3, 80, 22, 1, "pix"),
                    ("p_clines", "Lines between contrasting colors", 0, 1, 0.4, 0.01, "pix"),
                    ("p_tint", "Outline: black (0) <-> tinted (1)", 0, 1, 0.7, 0.01, "pix"),
                    ("p_odark", "Tinted outline darkness", 0.05, 1, 0.4, 0.01, "pix"),
                    ("p_feat", "Face / feature preserve", 0, 1, 0.7, 0.01, "pix"),
                    ("p_tones", "Outline tones (re-preps)", 1, 6, 3, 1, "pixprep"),
                    ("p_cut", "Thin-part coverage", 0.05, 0.95, 0.3, 0.01, "pix"),
                    ("p_detail", "Small-detail protect", 0, 1, 0.4, 0.01, "pix"),
                    ("p_speck", "Speckle cleanup (0=off)", 0, 1, 0.6, 0.01, "pix"),
                    ("p_smooth2", "Region smoothing", 0, 1, 0.0, 0.01, "pix")],
            t_pcol: [("p_sat", "Color pop before palette (re-preps)", 0.5, 2.5, 1.2, 0.01, "pixprep"),
                     ("p_con", "Contrast before palette (re-preps)", 0.7, 1.5, 1.05, 0.01, "pixprep"),
                     ("p_flat", "Flatten texture: median 0/3/5/7 (re-preps)", 0, 7, 0, 1, "pixprep"),
                     ("p_merge", "Merge similar colors (dE)", 0, 40, 9.0, 0.5, "pix"),
                     ("p_psat", "Saturation", 0, 2, 1.0, 0.01, "pix"),
                     ("p_pcon", "Contrast", 0.5, 1.5, 1.0, 0.01, "pix"),
                     ("p_bright", "Brightness", -80, 80, 0, 1, "pix")],
            t_bg: [("bg_tol", "Tolerance", 0, 120, 30, 1, "bg"),
                   ("bg_grow", "Edge trim (px, <0 keeps more)", -4, 8, 0, 1, "bg"),
                   ("bg_island", "Drop specks (fraction)", 0, 0.2, 0.02, 0.005, "bg")],
        }
        for tab, rows in spec.items():
            for key, text, lo, hi, val, step, kind in rows:
                w = FineSlider(tab, text, lo, hi, val, step,
                               (lambda k=kind: self.on_change(k)) if kind != "none" else (lambda: None))
                w.pack(fill="x", pady=2)
                self.f[key] = w
        ttk.Checkbutton(t_ref, text="GBA 15-bit palette snap", variable=self.c15,
                        command=lambda: self.on_change("render")).pack(anchor="w", pady=2)
        ttk.Button(t_grid, text="Reset grid", command=self.reset_grid).pack(fill="x", pady=4)
        ttk.Checkbutton(t_bg, text="Remove background", variable=self.bg_on,
                        command=lambda: self.on_change("bg")).pack(anchor="w", pady=2)
        mrow = ttk.Frame(t_bg)
        mrow.pack(fill="x", pady=2)
        ttk.Label(mrow, text="Mode").pack(side="left")
        mc = ttk.Combobox(mrow, textvariable=self.bg_mode, values=["edges", "color"], state="readonly", width=7)
        mc.pack(side="left", padx=4)
        mc.bind("<<ComboboxSelected>>", lambda e: self.on_change("bg"))
        ttk.Label(t_bg, text="edges: only background touching the border.\ncolor: also enclosed holes.",
                  wraplength=220).pack(anchor="w")
        ttk.Button(t_bg, text="Pick bg color (click Source)", command=self.start_pick).pack(fill="x", pady=2)
        ttk.Button(t_bg, text="Auto bg color", command=self.auto_color).pack(fill="x")
        ttk.Checkbutton(t_pix, text="Silhouette outline", variable=self.sil,
                        command=lambda: self.on_change("pix")).pack(anchor="w", pady=2)
        ttk.Checkbutton(t_pix, text="Clean outline corners (pixel-perfect)", variable=self.tidy,
                        command=lambda: self.on_change("pix")).pack(anchor="w", pady=2)
        ttk.Checkbutton(t_pix, text="Outline outside the shape (+1px)", variable=self.outer,
                        command=lambda: self.on_change("pix")).pack(anchor="w", pady=2)
        ttk.Checkbutton(t_pcol, text="GBA 15-bit palette snap", variable=self.c15,
                        command=lambda: self.on_change("pix")).pack(anchor="w", pady=2)

        self.go = ttk.Button(side, text="Analyze + Descale", command=self.analyze)
        self.go.pack(fill="x")
        ttk.Button(side, text="Re-render (discard edits)", command=self.force_refresh).pack(fill="x", pady=2)
        ttk.Button(side, text="Use result as descaler input", command=self.loop_to_descaler).pack(fill="x")
        ttk.Checkbutton(side, text="Gen 3 output (15 colors, 15-bit, near-black ink)", variable=self.gen3,
                        command=self.on_gen3).pack(anchor="w", pady=(6, 0))
        ttk.Button(side, text="Reset pixelizer sliders", command=self.reset_pix).pack(fill="x", pady=2)
        ttk.Button(side, text="Best input checklist…", command=self.show_checklist).pack(fill="x")
        ttk.Button(side, text="Save PNG…", command=self.save).pack(fill="x", pady=(6, 2))
        ttk.Button(side, text="Save big (x16) PNG…", command=self.save_big).pack(fill="x")
        ttk.Button(side, text="Save all 3 sizes…", command=self.save_all).pack(fill="x", pady=2)
        self.status = ttk.Label(side, text="Open an image.", wraplength=230)
        self.status.pack(anchor="w", pady=6)

        mid = ttk.Frame(self, padding=4)
        mid.grid(row=0, column=1, sticky="n")
        ttk.Label(mid, text="Source").pack()
        self.src_lbl = ttk.Label(mid)
        self.src_lbl.pack()
        self.src_lbl.bind("<Button-1>", self.on_src_click)
        ttk.Label(mid, text="Actual size").pack(pady=(8, 0))
        self.actual_lbl = ttk.Label(mid)
        self.actual_lbl.pack()
        ttk.Label(mid, text="Image advice").pack(pady=(8, 0))
        self.advice_txt = self._mk_text(mid, 11)
        ttk.Label(mid, text="Gen 3 check (64x64)").pack(pady=(6, 0))
        self.check_txt = self._mk_text(mid, 9)

        ed = ttk.Frame(self, padding=4)
        ed.grid(row=0, column=2, sticky="n")
        bar = ttk.Frame(ed)
        bar.pack(fill="x")
        for text, val in (("Pencil (P)", "pencil"), ("Eraser (E)", "eraser"),
                          ("Fill (F)", "fill"), ("Pick (I)", "pick")):
            ttk.Radiobutton(bar, text=text, value=val, variable=self.tool).pack(side="left", padx=2)
        ttk.Button(bar, text="Undo", width=6, command=self.do_undo).pack(side="left", padx=(10, 2))
        ttk.Button(bar, text="Redo", width=6, command=self.do_redo).pack(side="left")
        ttk.Button(bar, text="−", width=2, command=lambda: self.set_zoom(self.zoom - 2)).pack(side="left", padx=(10, 1))
        ttk.Button(bar, text="+", width=2, command=lambda: self.set_zoom(self.zoom + 2)).pack(side="left")
        ttk.Checkbutton(bar, text="Grid", variable=self.grid_on, command=self.redraw).pack(side="left", padx=8)
        ttk.Button(bar, text="GBA preview", command=self.open_gba).pack(side="left")

        self.canvas = tk.Canvas(ed, width=512, height=512, bg="#808080", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(pady=4)
        self.canvas.bind("<Button-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)
        self.canvas.bind("<Button-3>", self.on_pick)
        for key, val in (("p", "pencil"), ("e", "eraser"), ("f", "fill"), ("i", "pick")):
            self.canvas.bind(f"<{key}>", lambda e, v=val: self.tool.set(v))

        pal = ttk.Frame(ed)
        pal.pack(fill="x")
        self.cur_swatch = tk.Label(pal, width=4, relief="sunken", bg="#000000")
        self.cur_swatch.pack(side="left", padx=(0, 4))
        ttk.Button(pal, text="Custom…", command=self.custom_color).pack(side="left", padx=(0, 8))
        self.pal_frame = ttk.Frame(pal)
        self.pal_frame.pack(side="left", fill="x")
        self.pos_lbl = ttk.Label(ed, text="")
        self.pos_lbl.pack(anchor="w")

    # ---------- setting changes ----------
    def on_change(self, kind):
        delay = {"pix": 60, "pixprep": 400, "bg": 400}.get(kind, 60)
        if kind in self._after_ids:
            self.after_cancel(self._after_ids[kind])
        self._after_ids[kind] = self.after(delay, lambda: self._apply(kind))

    def _apply(self, kind):
        self._after_ids.pop(kind, None)
        if self.pix is None and self.state_ is None and self.px_src is None:
            return
        if self.dirty and kind != "none":
            self.status.config(text="Edits present. Use 'Re-render (discard edits)' to apply setting changes.")
            return
        if kind == "bg":
            self._show_src()
            if self.mode == "pixelize":
                self.run_pixelize()
            else:
                self.status.config(text="Background changed. Click 'Analyze + Descale' to apply.")
            return
        if kind in ("pix", "pixprep") or (kind == "size" and self.mode == "pixelize"):
            if self.mode == "pixelize":
                self.run_pixelize()
        elif self.mode == "descale" and self.state_:
            if kind == "grid":
                self.apply_grid()
            self.rerender(force=False)

    def force_refresh(self):
        if self.mode == "pixelize":
            self.dirty = False
            self.run_pixelize()
        else:
            self.rerender(force=True)

    def rparams(self):
        g = lambda k: self.f[k].get()
        return dict(detail=g("detail"), outline=g("outline"), speckle=g("speckle"), alpha_cut=g("alpha_cut"),
                    thin=g("thin"), merge=g("merge"), smooth=g("smooth"), sat=g("sat"),
                    contrast=g("contrast"), c15=self.c15.get())

    def apply_grid(self):
        g = lambda k: self.f[k].get()
        D.regrid(self.state_, g("gpx"), g("gpy"), g("gox"), g("goy"))

    def reset_grid(self):
        for k in ("gpx", "gpy", "gox", "goy"):
            self.f[k].set(self.f[k].default)
        if self.state_ and self.mode == "descale":
            self.on_change("grid")

    # ---------- load / analyze ----------
    def open(self):
        p = filedialog.askopenfilename(filetypes=[("Images", "*.png *.gif *.webp *.bmp *.jpg")])
        if p:
            self.load(p)

    def clean_src(self, base):
        """Background-removed copy of base if enabled (cached)."""
        if base is None or not self.bg_on.get():
            return base
        g = lambda k: self.f[k].get()
        key = (id(base), int(g("bg_tol")), int(g("bg_grow")), round(g("bg_island"), 4),
               self.bg_mode.get(), self.bg_color)
        if self._clean_cache and self._clean_cache[0] == key:
            return self._clean_cache[1]
        img = BG.remove_background(base, int(g("bg_tol")), self.bg_mode.get(), self.bg_color,
                                   int(g("bg_grow")), island=g("bg_island"))
        self._clean_cache = (key, img)
        return img

    @staticmethod
    def is_opaque(img):
        return bool(np.array(img.getchannel("A")).min() > 245)

    def start_pick(self):
        if self.src is None:
            return
        self.picking = True
        self.status.config(text="Click the background in the Source picture.")

    def auto_color(self):
        self.bg_color = None
        self.on_change("bg")

    def on_src_click(self, e):
        if not self.picking or self.src is None:
            return
        self.picking = False
        sw, sh = self.src.size
        f = min(SRC_PREVIEW / sw, SRC_PREVIEW / sh)
        x, y = int(e.x / f), int(e.y / f)
        if 0 <= x < sw and 0 <= y < sh:
            self.bg_color = tuple(int(v) for v in self.src.getpixel((x, y))[:3])
            self.bg_on.set(True)
            self.status.config(text=f"Background color set to {self.bg_color}.")
            self.on_change("bg")

    def load(self, p):
        self.path = p
        self.src = Image.open(p).convert("RGBA")
        self.px_src = None
        self.bg_color = None
        self.bg_on.set(self.is_opaque(self.src))  # opaque image -> assume a background to remove
        self._show_src()
        self.start_advice(self.src)
        self.analyze()

    def _show_src(self):
        im = self.clean_src(self.src).copy()
        im.thumbnail((SRC_PREVIEW, SRC_PREVIEW), Image.LANCZOS)
        bg = Image.new("RGBA", im.size, (200, 200, 200, 255))
        bg.alpha_composite(im)
        self._src_tk = ImageTk.PhotoImage(bg)
        self.src_lbl.configure(image=self._src_tk)

    def analyze(self):
        if self.src is None:
            self.status.config(text="Open a sprite first (or use 'Use result as descaler input').")
            return
        if self.dirty and not messagebox.askyesno("Discard edits?", "Re-analyzing replaces your pixel edits. Continue?"):
            return
        self.mode = "descale"
        self.show_tabs()
        self.go.state(["disabled"])
        self.status.config(text="Analyzing… (slow)")
        colors, light, src = self.colors.get(), self.f["light"].get(), self.clean_src(self.src)

        def work():
            D.LIGHT_WEIGHT = light
            try:
                st = D.analyze(src, 64, 64, colors)
                self.q.put(("done", st))
            except Exception as e:  # surface to UI
                self.q.put(("error", e))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                self.go.state(["!disabled"])
                if kind == "error":
                    self.px_busy = False
                    self.status.config(text=f"Error: {val}")
                elif kind == "advice":
                    items, rec = val
                    self.show_advice(items)
                    if rec != self.mode and rec == "descale":
                        self.status.config(text="This looks like pixel art: 'Open sprite (descale)' will do better.")
                    continue
                elif kind == "pix":
                    img, pst, key = val
                    self.px_busy = False
                    if pst is not None:
                        self.px_state, self.px_key = pst, key
                    if self.px_pending:
                        self.px_pending = False
                        self.run_pixelize()
                    self.pix = np.array(self._finish(img))
                    self.undo.clear()
                    self.redo.clear()
                    self.dirty = False
                    self.zoom = max(4, min(24, 512 // max(self.pix.shape[:2])))
                    self.status.config(text="Pixelized. Tweak sliders, edit, or 'Use result as descaler input'.")
                    self.redraw()
                    self.refresh_palette()
                else:
                    self.state_ = val
                    self.dirty = False
                    for k in ("gpx", "gpy", "gox", "goy"):
                        self.f[k].set(self.f[k].default)
                    self.status.config(text="Done. Edit pixels on the right." if val else "Image is empty.")
                    self.rerender(force=True)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ---------- pixelize ----------
    def pixelize_open(self):
        p = filedialog.askopenfilename(filetypes=[("Images", "*.png *.gif *.webp *.bmp *.jpg *.jpeg")])
        if not p:
            return
        if self.dirty and not messagebox.askyesno("Discard edits?", "Opening artwork replaces your pixel edits. Continue?"):
            return
        self.path = p
        self.px_src = Image.open(p).convert("RGBA")
        self.mode = "pixelize"
        self.show_tabs()
        self.dirty = False
        self.src = self.px_src
        self.bg_color = None
        self.bg_on.set(self.is_opaque(self.src))
        self._show_src()
        self.start_advice(self.src)
        self.run_pixelize()

    def run_pixelize(self):
        """Slow stage (fit/palette) only when its inputs changed; look sliders just re-render."""
        if self.px_src is None:
            return
        if self.px_busy:  # coalesce rapid slider moves into one trailing run
            self.px_pending = True
            return
        tw, th = D.SIZES[self.size.get()]
        g = lambda k: self.f[k].get()
        src = self.clean_src(self.px_src)
        self._px_clean_ref = src  # keep alive so id() in the cache key stays unique
        prep = dict(colors=self.colors.get(), margin=max(1, int(self.margin.get())), smooth=int(g("p_flat")),
                    sat=g("p_sat"), contrast=g("p_con"), tones=int(g("p_tones")))
        key = (id(src), tw, th, tuple(sorted(prep.items())))
        rkw = dict(line=g("p_line"), silhouette=self.sil.get(), detail=g("p_detail"), alpha_cut=g("p_cut"),
                   speckle=g("p_speck"), smooth=g("p_smooth2"), merge=g("p_merge"), outline_dark=g("p_odark"),
                   line_abs=g("p_labs"), line_rel=g("p_lrel"), outer=self.outer.get(), post_sat=g("p_psat"),
                   post_contrast=g("p_pcon"), bright=int(g("p_bright")), c15=self.c15.get(),
                   contrast_lines=g("p_clines"), tint=g("p_tint"), feature=g("p_feat"), tidy=self.tidy.get())
        old_state = self.px_state if key == self.px_key else None
        self.px_busy = True
        self.status.config(text="Pixelizing…" if old_state is None else "Updating…")

        def work():
            try:
                st = old_state
                if st is None:
                    st = PX.prepare(src, tw, th, auto_bg=False, **prep)
                if st is None:
                    self.q.put(("pix", (Image.new("RGBA", (tw, th), (0, 0, 0, 0)), None, None)))
                    return
                self.q.put(("pix", (PX.render(st, **rkw), st, key)))
            except Exception as e:
                self.q.put(("error", e))
        threading.Thread(target=work, daemon=True).start()

    # ---------- advice / checks / gen3 output ----------
    @staticmethod
    def _mk_text(parent, height):
        t = tk.Text(parent, width=44, height=height, wrap="word", font=("Segoe UI", 8), relief="flat",
                    bg="#f4f4f4", state="disabled")
        t.tag_configure("good", foreground="#1b7a1b")
        t.tag_configure("tip", foreground="#9a6a00")
        t.tag_configure("warn", foreground="#b00020")
        t.tag_configure("flag", foreground="#b00020")
        t.tag_configure("watch", foreground="#9a6a00")
        t.tag_configure("ok", foreground="#1b7a1b")
        t.tag_configure("dim", foreground="#666666")
        t.pack()
        return t

    @staticmethod
    def _set_text(t, parts):
        t.config(state="normal")
        t.delete("1.0", "end")
        for text, tag in parts:
            t.insert("end", text, tag)
        t.config(state="disabled")

    def start_advice(self, img):
        self._set_text(self.advice_txt, [("Analyzing image…", "dim")])
        tw, th = D.SIZES[self.size.get()]

        def work():
            try:
                self.q.put(("advice", (AD.advise(img, (tw, th)), AD.recommend_mode(img))))
            except Exception as e:
                self.q.put(("advice", ([("tip", "Advice unavailable", str(e))], self.mode)))
        threading.Thread(target=work, daemon=True).start()

    def show_advice(self, items):
        tag = {"good": "OK ", "tip": "TIP", "warn": "!! "}
        parts = []
        for lvl, title, detail in items:
            parts.append((f"{tag[lvl]} {title}\n", lvl))
            if detail:
                parts.append((f"    {detail}\n", "dim"))
        self._set_text(self.advice_txt, parts)

    def show_checklist(self):
        w = tk.Toplevel(self)
        w.title("Best input checklist")
        t = tk.Text(w, width=88, height=20, wrap="word", font=("Consolas", 9))
        t.insert("1.0", AD.CHECKLIST)
        t.config(state="disabled")
        t.pack(padx=8, pady=8)

    def _finish(self, img):
        """Final Gen 3 stage: 15-bit colour, <=15 colours, near-black ink."""
        if not self.gen3.get():
            return img
        out, info = GBA.finalize(img)
        if info["merged"]:
            self.status.config(text=f"Gen 3 output: merged {info['merged']} colors to fit 15.")
        return out

    def on_gen3(self):
        if self.mode == "pixelize":
            self.on_change("pix")
        elif self.state_ is not None:
            self.on_change("render")

    def show_tabs(self):
        """Only list tabs that apply to the current mode."""
        keep = self.tabs_for[self.mode]
        cur = self.nb.select()
        for f, name in self.all_tabs:
            if f in keep:
                if str(f) not in self.nb.tabs():
                    self.nb.add(f, text=name)
            elif str(f) in self.nb.tabs():
                self.nb.forget(f)
        order = [f for f, _ in self.all_tabs if f in keep]
        for i, f in enumerate(order):
            self.nb.insert(i, f)
        if cur not in self.nb.tabs():
            self.nb.select(order[0])

    def reset_pix(self):
        for k, w in self.f.items():
            if k.startswith("p_"):
                w.set(w.default)
        self.sil.set(True)
        self.outer.set(False)
        self.tidy.set(True)
        if self.mode == "pixelize":
            self.on_change("pixprep")

    def _sched_check(self):
        if self._chk_id is not None:
            self.after_cancel(self._chk_id)
        self._chk_id = self.after(300, self.run_check)

    def run_check(self):
        self._chk_id = None
        if self.pix is None:
            return
        h, w = self.pix.shape[:2]
        if (w, h) != (64, 64):
            self._set_text(self.check_txt, [(f"Reference ranges were measured on 64x64 sprites.\nSwitch Size to 64x64 for the check.", "dim")])
            return
        rows = MT.check(Image.fromarray(self.pix, "RGBA"))
        bad = [r for r in rows if r[4] != "ok"]
        parts = [(f"{len(rows) - len(bad)}/{len(rows)} measures match real Gen 3 sprites\n", "ok" if not bad else "dim")]
        for name, v, lo, hi, status, hint in sorted(bad, key=lambda r: r[4] != "flag"):
            parts.append((f"{'!!' if status == 'flag' else '..'} {name} {v:.2f} (real {lo:.2f}-{hi:.2f})\n", status))
            if hint:
                parts.append((f"    {hint}\n", "dim"))
        self._set_text(self.check_txt, parts)

    def loop_to_descaler(self):
        """Blow current pixel art up (nearest) and use it as descaler input."""
        if self.pix is None:
            return
        big = Image.fromarray(self.pix, "RGBA")
        big = big.resize((big.width * 16, big.height * 16), Image.NEAREST)
        self.src = big
        self.bg_on.set(False)  # already transparent
        self._show_src()
        self.dirty = False
        self.analyze()

    # ---------- render ----------
    def rerender(self, force):
        if not self.state_ or self.mode != "descale":
            return
        if self.dirty and not force:
            self.status.config(text="Edits present. Use 'Re-render (discard edits)' to apply setting changes.")
            return
        tw, th = D.SIZES[self.size.get()]
        self.state_["tw"], self.state_["th"] = tw, th
        self.state_["margin"] = int(self.margin.get())
        if force:
            self.apply_grid()
        img = D.render(self.state_, **self.rparams())
        self.pix = np.array(self._finish(img))
        self.undo.clear()
        self.redo.clear()
        self.dirty = False
        self.zoom = max(4, min(24, 512 // max(tw, th)))
        self.redraw()
        self.refresh_palette()

    def open_gba(self):
        if self.gba is not None and self.gba.winfo_exists():
            self.gba.lift()
            return
        self.gba = GbaPreview(self)

    def _gba_refresh(self):
        if self.gba is not None and self.gba.winfo_exists():
            self.gba.refresh()

    def set_zoom(self, z):
        self.zoom = max(4, min(32, z))
        self.redraw()

    def redraw(self):
        if self.pix is None:
            return
        h, w = self.pix.shape[:2]
        z = self.zoom
        # checkerboard + image
        yy, xx = np.mgrid[0:h * z, 0:w * z]
        chk = np.where(((yy // (z // 2 or 1)) + (xx // (z // 2 or 1))) % 2 == 0, 205, 235).astype(np.uint8)
        bg = Image.fromarray(np.stack([chk, chk, chk, np.full_like(chk, 255)], -1), "RGBA")
        big = Image.fromarray(self.pix, "RGBA").resize((w * z, h * z), Image.NEAREST)
        bg.alpha_composite(big)
        if self.grid_on.get() and z >= 8:
            arr = np.array(bg)
            arr[::z, :, :3] = (arr[::z, :, :3] * 0.75).astype(np.uint8)
            arr[:, ::z, :3] = (arr[:, ::z, :3] * 0.75).astype(np.uint8)
            bg = Image.fromarray(arr, "RGBA")
        self._tk = ImageTk.PhotoImage(bg)
        self.canvas.config(width=w * z, height=h * z)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._tk, anchor="nw")
        actual = Image.new("RGBA", (w, h), (200, 200, 200, 255))
        actual.alpha_composite(Image.fromarray(self.pix, "RGBA"))
        self._actual_tk = ImageTk.PhotoImage(actual.resize((w * 2, h * 2), Image.NEAREST))
        self.actual_lbl.configure(image=self._actual_tk)
        self._gba_refresh()
        self._sched_check()

    def refresh_palette(self):
        for c in self.pal_frame.winfo_children():
            c.destroy()
        if self.pix is None:
            return
        px = self.pix.reshape(-1, 4)
        px = px[px[:, 3] > 0]
        if len(px) == 0:
            return
        cols, counts = np.unique(px, axis=0, return_counts=True)
        for c in cols[np.argsort(-counts)][:24]:
            hexc = "#%02x%02x%02x" % tuple(c[:3])
            b = tk.Label(self.pal_frame, width=2, bg=hexc, relief="raised", bd=1)
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, c=tuple(int(v) for v in c): self.set_color(c))

    def set_color(self, c):
        self.color = (c[0], c[1], c[2], 255)
        self.cur_swatch.config(bg="#%02x%02x%02x" % self.color[:3])
        if self.tool.get() in ("eraser", "pick"):
            self.tool.set("pencil")

    def custom_color(self):
        rgb, _ = colorchooser.askcolor(color="#%02x%02x%02x" % self.color[:3])
        if rgb:
            self.set_color(tuple(int(v) for v in rgb))

    # ---------- editing ----------
    def cell(self, e):
        if self.pix is None:
            return None
        x, y = e.x // self.zoom, e.y // self.zoom
        h, w = self.pix.shape[:2]
        return (x, y) if 0 <= x < w and 0 <= y < h else None

    def push_undo(self):
        self.undo.append(self.pix.copy())
        if len(self.undo) > UNDO_LIMIT:
            self.undo.pop(0)
        self.redo.clear()

    def do_undo(self):
        if self.undo:
            self.redo.append(self.pix.copy())
            self.pix = self.undo.pop()
            self.dirty = True
            self.redraw()
            self.refresh_palette()

    def do_redo(self):
        if self.redo:
            self.undo.append(self.pix.copy())
            self.pix = self.redo.pop()
            self.dirty = True
            self.redraw()
            self.refresh_palette()

    def on_down(self, e):
        self.canvas.focus_set()
        c = self.cell(e)
        if c is None:
            return
        t = self.tool.get()
        if t == "pick":
            return self.pick_at(c)
        self.push_undo()
        self.last_cell = c
        if t == "fill":
            self.flood(c)
        else:
            self.paint(c)
        self.dirty = True
        self.redraw()

    def on_drag(self, e):
        c = self.cell(e)
        t = self.tool.get()
        if c is None or t in ("fill", "pick"):
            return
        a = self.last_cell or c
        for p in self.line(a, c):
            self.paint(p)
        self.last_cell = c
        self.redraw()

    def on_up(self, e):
        self.last_cell = None
        if self.tool.get() in ("pencil", "eraser", "fill"):
            self.refresh_palette()

    def on_pick(self, e):
        c = self.cell(e)
        if c:
            self.pick_at(c)

    def pick_at(self, c):
        p = self.pix[c[1], c[0]]
        if p[3] > 0:
            self.set_color(tuple(int(v) for v in p[:3]))
            self.tool.set("pencil")
        self.pos_lbl.config(text=f"({c[0]},{c[1]})  rgba{tuple(int(v) for v in p)}")

    def paint(self, c):
        x, y = c
        self.pix[y, x] = (0, 0, 0, 0) if self.tool.get() == "eraser" else self.color

    @staticmethod
    def line(a, b):
        (x0, y0), (x1, y1) = a, b
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            yield x0, y0
            if (x0, y0) == (x1, y1):
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def flood(self, c):
        h, w = self.pix.shape[:2]
        x, y = c
        target = self.pix[y, x].copy()
        new = np.array(self.color, np.uint8)
        if (target == new).all():
            return
        dq = deque([(x, y)])
        while dq:
            cx, cy = dq.popleft()
            if not (0 <= cx < w and 0 <= cy < h) or not (self.pix[cy, cx] == target).all():
                continue
            self.pix[cy, cx] = new
            dq.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))

    # ---------- save ----------
    def save(self):
        if self.pix is None:
            return
        init = f"{Path(self.path).stem}_{self.size.get()}.png"
        p = filedialog.asksaveasfilename(defaultextension=".png", initialfile=init,
                                         filetypes=[("PNG", "*.png")])
        if p:
            Image.fromarray(self.pix, "RGBA").save(p)
            self.status.config(text=f"Saved {Path(p).name}")

    def save_big(self):
        if self.pix is None:
            return
        init = f"{Path(self.path).stem}_x16.png"
        p = filedialog.asksaveasfilename(defaultextension=".png", initialfile=init, filetypes=[("PNG", "*.png")])
        if p:
            im = Image.fromarray(self.pix, "RGBA")
            im.resize((im.width * 16, im.height * 16), Image.NEAREST).save(p)
            self.status.config(text=f"Saved {Path(p).name}")

    def save_all(self):
        if self.mode == "pixelize":
            self.status.config(text="Save all sizes works in descale mode. Use 'Use result as descaler input' first.")
            return
        if self.state_ is None:
            return
        d = filedialog.askdirectory(title="Save 64x64, 32x32, 16x32 to…")
        if not d:
            return
        for name in ("64x64", "32x32", "16x32"):
            tw, th = D.SIZES[name]
            self.state_["tw"], self.state_["th"] = tw, th
            self.state_["margin"] = int(self.margin.get())
            D.render(self.state_, **self.rparams()).save(Path(d) / f"{Path(self.path).stem}_{name}.png")
        tw, th = D.SIZES[self.size.get()]
        self.state_["tw"], self.state_["th"] = tw, th
        self.status.config(text=f"Saved 3 sizes to {d} (auto-rendered, edits not included).")


if __name__ == "__main__":
    App(sys.argv[1] if len(sys.argv) > 1 else None).mainloop()
