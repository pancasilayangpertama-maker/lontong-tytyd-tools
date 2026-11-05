"""Colours, fonts and DPI scaling.

Three looks share one layout: amber (the start look and Balance), blue (Santai) and red (Gaming).
Only the gradient behind the window and the menu change colour; the cards stay the same.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from typing import List, Tuple

CARD = "#FFFBF2"       # the big content card
PANEL = "#FFFFFF"      # white boxes inside the card
LINE = "#F0DCB0"       # hairlines
INK = "#2B1A05"        # main text
MUTED = "#7A6240"      # secondary text
SOFT = "#FFF0C9"       # quiet button
SOFT_HOVER = "#FFE19A"
OFF = "#E3D6B8"        # switched-off switch, disabled button
GREEN = "#2E9E5B"
ORANGE = "#F97316"     # accent for buttons that are not tied to a mode
DANGER = "#D93025"
TERM_BG = "#0E1218"    # the Log page is a terminal, like in the reference video
TERM_LINE = "#1E2733"
TERM_HEAD = "#5E9C7A"


@dataclass(frozen=True)
class Look:
    name: str
    top: str       # gradient, top colour
    bottom: str    # gradient, bottom colour
    ink: str       # text drawn straight on the gradient
    pill: str      # fill behind the selected menu entry
    strong: str    # text on that pill
    accent: str    # buttons and badges that belong to this look


LOOKS = {
    "amber": Look("amber", "#FFD93D", "#FF8A1C", "#3A2300", "#FFF7E2", "#8A4300", "#F97316"),
    "blue": Look("blue", "#3B82F6", "#1E3A8A", "#FFFFFF", "#EAF3FF", "#1D4ED8", "#2563EB"),
    "red": Look("red", "#EF4444", "#7F1D1D", "#FFFFFF", "#FFEDE9", "#B91C1C", "#DC2626"),
}

SCALE = 1.0
_FONTS: List[tkfont.Font] = []  # a named font disappears when its Font object is garbage collected: keep them


def px(value: float) -> int:
    """Scale a design pixel to the real screen (high-DPI laptops)."""
    return max(1, int(round(value * SCALE)))


def rgb(hex_color: str) -> Tuple[int, int, int]:
    return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)


def hexa(color: Tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in color)
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def shade(hex_color: str, factor: float) -> str:
    return hexa(tuple(c * factor for c in rgb(hex_color)))  # type: ignore[arg-type]


def init(root: tk.Misc) -> None:
    """Call once, right after the Tk root exists."""
    global SCALE
    try:
        SCALE = max(1.0, float(root.winfo_fpixels("1i")) / 96.0)
    except Exception:
        SCALE = 1.0
    families = set(tkfont.families(root))

    def pick(*names: str) -> str:
        for name in names:
            if name in families:
                return name
        return tkfont.nametofont("TkDefaultFont").actual("family")

    head = pick("Segoe UI Semibold", "Segoe UI", "Helvetica", "Arial")
    body = pick("Segoe UI", "Helvetica", "Arial")
    mono = pick("Cascadia Mono", "Consolas", "Courier New")
    specs = {
        "ix9.title": (head, 17, "bold"),
        "ix9.h1": (head, 14, "bold"),
        "ix9.h2": (head, 11, "bold"),
        "ix9.brand": (head, 14, "bold"),
        "ix9.nav": (head, 11, "normal"),
        "ix9.navb": (head, 11, "bold"),
        "ix9.btn": (head, 10, "bold"),
        "ix9.body": (body, 10, "normal"),
        "ix9.bodyb": (body, 10, "bold"),
        "ix9.small": (body, 9, "normal"),
        "ix9.mono": (mono, 10, "normal"),
    }
    del _FONTS[:]
    for name, (family, size, weight) in specs.items():
        try:
            font = tkfont.Font(root=root, name=name, family=family, size=size, weight=weight)
        except tk.TclError:  # already defined (second call): just update it
            font = tkfont.nametofont(name, root=root)
            font.configure(family=family, size=size, weight=weight)
        _FONTS.append(font)
