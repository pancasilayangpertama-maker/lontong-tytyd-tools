"""Small custom widgets. Plain Tk only; everything that moves is drawn on a Canvas."""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import theme as T

SIDEBAR = 208  # width of the menu column, in design pixels


class AutoLabel(tk.Label):
    """Left-aligned label that re-wraps its text to whatever width it is given."""

    def __init__(self, master: tk.Misc, text: str = "", **kw) -> None:
        kw.setdefault("justify", "left")
        kw.setdefault("anchor", "w")
        kw.setdefault("wraplength", T.px(300))
        super().__init__(master, text=text, **kw)
        self.bind("<Configure>", self._fit)

    def _fit(self, event) -> None:
        width = max(T.px(60), int(event.width) - 2)
        if abs(int(float(self.cget("wraplength"))) - width) > 2:
            self.configure(wraplength=width)


class Btn(tk.Label):
    """Flat button. kind='solid' is filled with `color`; kind='soft' is the quiet version."""

    def __init__(self, master: tk.Misc, text: str, command: Optional[Callable[[], object]] = None,
                 color: str = T.ORANGE, kind: str = "solid") -> None:
        self._kind = kind
        self._color = color
        self._command = command
        self._enabled = True
        super().__init__(master, text=text, font="ix9.btn", cursor="hand2",
                         padx=T.px(16), pady=T.px(8), bd=0, highlightthickness=0)
        self._paint(False)
        self.bind("<Enter>", lambda _e: self._paint(True))
        self.bind("<Leave>", lambda _e: self._paint(False))
        self.bind("<ButtonRelease-1>", self._release)

    def _paint(self, hover: bool) -> None:
        if not self._enabled:
            fill, ink = T.OFF, "#9A8B6A"
        elif self._kind == "soft":
            fill, ink = (T.SOFT_HOVER if hover else T.SOFT), T.INK
        else:
            fill, ink = (T.shade(self._color, 0.86) if hover else self._color), "#FFFFFF"
        self.configure(bg=fill, fg=ink, cursor="hand2" if self._enabled else "arrow")

    def _release(self, event) -> None:
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if self._enabled and inside and self._command:
            self._command()

    def set_text(self, text: str) -> None:
        self.configure(text=text)

    def enable(self, flag: bool) -> None:
        self._enabled = bool(flag)
        self._paint(False)


class Switch(tk.Canvas):
    """On/off switch. `command(wanted_state)` may return False to refuse the click."""

    def __init__(self, master: tk.Misc, command: Optional[Callable[[bool], object]] = None,
                 bg: str = T.PANEL, on_color: str = T.ORANGE) -> None:
        self._sw, self._sh = T.px(44), T.px(24)
        super().__init__(master, width=self._sw, height=self._sh, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self._on = False
        self._on_color = on_color
        self._command = command
        self.bind("<Button-1>", self._click)
        self._draw()

    def get(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        if bool(on) != self._on:
            self._on = bool(on)
            self._draw()

    def _click(self, _event) -> None:
        wanted = not self._on
        if self._command is not None and self._command(wanted) is False:
            return
        self.set(wanted)

    def _draw(self) -> None:
        self.delete("all")
        w, h = self._sw, self._sh
        track = self._on_color if self._on else T.OFF
        self.create_oval(0, 0, h, h, fill=track, width=0, outline="")
        self.create_oval(w - h, 0, w, h, fill=track, width=0, outline="")
        self.create_rectangle(h / 2, 0, w - h / 2, h, fill=track, width=0, outline="")
        pad = T.px(3)
        d = h - 2 * pad
        x = (w - pad - d) if self._on else pad
        self.create_oval(x, pad, x + d, pad + d, fill="#FFFFFF", width=0, outline="")


class Lamp(tk.Canvas):
    """Status lamp in the header."""

    def __init__(self, master: tk.Misc, bg: str = T.CARD) -> None:
        d = T.px(10)
        super().__init__(master, width=d, height=d, bg=bg, highlightthickness=0, bd=0)
        self._d = d
        self.set(T.GREEN)

    def set(self, color: str) -> None:
        self.delete("all")
        self.create_oval(0, 0, self._d, self._d, fill=color, width=0, outline="")


class ScrollFrame(tk.Frame):
    """A vertically scrolling area. Put children into `.inner`. The mouse wheel is routed by the app."""

    def __init__(self, master: tk.Misc, bg: str = T.CARD) -> None:
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=T.px(24))
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Ix9.Vertical.TScrollbar")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._window, width=e.width))

    def wheel(self, delta: int) -> None:
        if tuple(self.canvas.yview()) == (0.0, 1.0):
            return  # everything already fits
        steps = max(1, abs(int(delta)) // 40)
        self.canvas.yview_scroll(-steps if delta > 0 else steps, "units")

    def clear(self) -> None:
        for child in list(self.inner.winfo_children()):
            child.destroy()
        self.canvas.yview_moveto(0)


class LogView(tk.Frame):
    """The Log page: a terminal with one line per event, like the Activity Log in the reference video."""

    GREEN = "#4ADE80"
    LEVELS = {
        "info": ("INFO", "#4ADE80"),
        "ok": ("OK", "#A3E635"),
        "warn": ("WARN", "#FACC15"),
        "err": ("ERROR", "#F87171"),
        "dim": ("DEBUG", "#3F8F63"),
    }

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=T.TERM_BG, highlightthickness=1, highlightbackground=T.TERM_LINE,
                         highlightcolor=T.TERM_LINE)
        tk.Label(self, text="DIAGNOSTIC EVENT LOG", font="ix9.small", fg=T.TERM_HEAD, bg=T.TERM_BG,
                 anchor="w").pack(fill="x", padx=T.px(14), pady=(T.px(10), T.px(2)))
        body = tk.Frame(self, bg=T.TERM_BG)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, bg=T.TERM_BG, fg=self.GREEN, insertbackground=self.GREEN, bd=0,
                            highlightthickness=0, wrap="word", font="ix9.mono", state="disabled",
                            padx=T.px(14), pady=T.px(8), relief="flat")
        bar = ttk.Scrollbar(body, orient="vertical", command=self.text.yview, style="Ix9Dark.Vertical.TScrollbar")
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("time", foreground=T.TERM_HEAD)
        for key, (_label, color) in self.LEVELS.items():
            self.text.tag_configure(f"lv_{key}", foreground=color)

    def add(self, message: str, level: str = "info") -> None:
        key = level if level in self.LEVELS else "info"
        label = self.LEVELS[key][0]
        self.text.configure(state="normal")
        self.text.insert("end", f"[{time.strftime('%H:%M:%S')}] ", "time")
        self.text.insert("end", f"[{label}] {message}\n", f"lv_{key}")
        total = int(self.text.index("end-1c").split(".")[0])
        if total > 800:
            self.text.delete("1.0", f"{total - 700}.0")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


# --------------------------------------------------------------------------- gradient backdrop + menu


class Backdrop(tk.Canvas):
    """The whole window: a vertical gradient with the content card on top. It changes colour with the mode."""

    STRIPS = 64

    def __init__(self, master: tk.Misc, look: T.Look) -> None:
        super().__init__(master, highlightthickness=0, bd=0, bg=look.top)
        self.look = look
        self.extent = (1, 1)  # current width, height in real pixels
        self._shown = (T.rgb(look.top), T.rgb(look.bottom))
        self._job: Optional[str] = None
        self._hooks: List[Callable[[int, int], None]] = []
        self.strips = [self.create_rectangle(0, 0, 1, 1, fill=look.top, width=0, outline="", tags=("bg",))
                       for _ in range(self.STRIPS)]
        self.card = tk.Frame(self, bg=T.CARD, highlightthickness=1, highlightbackground=T.LINE,
                             highlightcolor=T.LINE, bd=0)
        self._card_item = self.create_window(0, 0, window=self.card, anchor="nw")
        self.bind("<Configure>", self._on_resize)
        self._paint(self._shown)

    def add_hook(self, hook: Callable[[int, int], None]) -> None:
        self._hooks.append(hook)

    def _on_resize(self, event) -> None:
        w, h = max(int(event.width), 2), max(int(event.height), 2)
        self.extent = (w, h)
        step = h / self.STRIPS
        for i, item in enumerate(self.strips):
            self.coords(item, 0, i * step, w, (i + 1) * step + 1)
        pad = T.px(16)
        left = T.px(SIDEBAR)
        self.coords(self._card_item, left, pad)
        self.itemconfigure(self._card_item, width=max(T.px(300), w - left - pad), height=max(T.px(200), h - 2 * pad))
        for hook in self._hooks:
            hook(w, h)

    def _paint(self, colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]]) -> None:
        top, bottom = colors
        last = max(1, self.STRIPS - 1)
        for i, item in enumerate(self.strips):
            self.itemconfigure(item, fill=T.hexa(T.mix(top, bottom, i / last)))

    def set_look(self, look: T.Look, animate: bool = True) -> None:
        """Fade the gradient to a new look (about a quarter of a second)."""
        self.look = look
        target = (T.rgb(look.top), T.rgb(look.bottom))
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if not animate or self._shown == target:
            self._shown = target
            self._paint(target)
            return
        start = self._shown
        steps = 12

        def frame(i: int) -> None:
            t = i / steps
            self._shown = (T.mix(start[0], target[0], t), T.mix(start[1], target[1], t))
            self._paint(self._shown)
            self._job = self.after(22, lambda: frame(i + 1)) if i < steps else None

        frame(1)


def _round_rect(x0: float, y0: float, x1: float, y1: float, r: float) -> List[float]:
    """Points for a smooth polygon that draws a rounded rectangle."""
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1,
            x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]


class Nav:
    """The menu, drawn straight onto the gradient: brand on top, pages in the middle, Log at the very bottom."""

    ROW = 42

    def __init__(self, canvas: Backdrop, entries: Sequence[Tuple[str, str]], last_key: str,
                 on_pick: Callable[[str], None], logo: Optional[tk.PhotoImage], brand: str, tagline: str) -> None:
        self.cv = canvas
        self.entries = list(entries)
        self.last_key = last_key
        self.on_pick = on_pick
        self.active: Optional[str] = None
        self.items: Dict[str, Tuple[int, int]] = {}
        self.rows: Dict[str, Tuple[float, float]] = {}  # key -> (top, bottom) in real pixels, set by layout()
        look = canvas.look
        if logo is not None:
            canvas.create_image(T.px(20), T.px(20), image=logo, anchor="nw")
        self.brand = canvas.create_text(T.px(20), T.px(92), text=brand, font="ix9.brand", fill=look.ink, anchor="nw")
        self.tagline = canvas.create_text(T.px(20), T.px(116), text=tagline, font="ix9.small", fill=look.ink, anchor="nw")
        for key, label in self.entries:
            pill = canvas.create_polygon(0, 0, 0, 0, 0, 0, smooth=True, splinesteps=12, fill=look.pill,
                                         outline="", state="hidden")
            text = canvas.create_text(0, 0, text=label, font="ix9.nav", fill=look.ink, anchor="w")
            self.items[key] = (pill, text)
        # one click handler for the whole menu: the full row is clickable, not only the letters
        canvas.bind("<Button-1>", self._click, add="+")
        canvas.bind("<Motion>", self._hover, add="+")
        canvas.bind("<Leave>", lambda _e: canvas.configure(cursor=""), add="+")
        canvas.add_hook(self.layout)

    def _hit(self, event) -> Optional[str]:
        if not (T.px(12) <= event.x <= T.px(SIDEBAR) - T.px(10)):
            return None
        for key, (top, bottom) in self.rows.items():
            if top <= event.y <= bottom:
                return key
        return None

    def _click(self, event) -> None:
        key = self._hit(event)
        if key is not None:
            self.on_pick(key)

    def _hover(self, event) -> None:
        self.cv.configure(cursor="hand2" if self._hit(event) is not None else "")

    def layout(self, width: int, height: int) -> None:
        left, right = T.px(12), T.px(SIDEBAR) - T.px(10)
        row = T.px(self.ROW)
        y = T.px(158)
        for key, _label in self.entries:
            if key == self.last_key:
                continue
            self._place(key, y, row, left, right)
            y += row + T.px(4)
        self._place(self.last_key, height - T.px(22) - row, row, left, right)

    def _place(self, key: str, y: float, row: float, left: float, right: float) -> None:
        pill, text = self.items[key]
        self.rows[key] = (y, y + row)
        self.cv.coords(pill, *_round_rect(left, y, right, y + row, T.px(12)))
        self.cv.coords(text, left + T.px(20), y + row / 2)

    def set_active(self, key: Optional[str]) -> None:
        self.active = key
        look = self.cv.look
        for name, (pill, text) in self.items.items():
            on = name == key
            self.cv.itemconfigure(pill, state="normal" if on else "hidden", fill=look.pill)
            self.cv.itemconfigure(text, fill=look.strong if on else look.ink, font="ix9.navb" if on else "ix9.nav")

    def apply_look(self, look: T.Look) -> None:
        self.cv.itemconfigure(self.brand, fill=look.ink)
        self.cv.itemconfigure(self.tagline, fill=look.ink)
        self.set_active(self.active)
