"""The Marshall IX9 window. Long jobs run in a worker thread; the UI only changes on the main thread."""
from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional

from . import APP_NAME, __version__
from .core import modes, power
from .core import tweaks as tw
from .core import winutil as wu
from .ui import theme as T
from .ui.pages import AppsPage, CleanerPage, LogPage, ModePage, Page, SafetyPage
from .ui.widgets import Backdrop, Btn, Lamp, Nav, ScrollFrame

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]


def resource_path(relative: str) -> str:
    """Find a bundled file, both when run from source and from the PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def write_error_log(text: str) -> str:
    path = os.path.join(wu.data_dir(), "error.log")
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{text}\n")
    except OSError:
        pass
    return path


def _enable_dpi_awareness() -> None:
    if not wu.IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class App(tk.Tk):
    PAGES = (("mode", "Mode"), ("cleaner", "Pembersih"), ("apps", "Aplikasi"), ("safety", "Keamanan"), ("log", "Log"))

    def __init__(self) -> None:
        _enable_dpi_awareness()
        super().__init__()
        self.withdraw()  # no flash while the window is being built
        T.init(self)
        self.title(f"{APP_NAME} - PC Optimizer")
        self.configure(bg=T.LOOKS["amber"].top)
        self._size_window()
        self._set_icon()
        self._style_scrollbars()

        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.busy = False
        self.backup = wu.BackupStore()
        self.tweaks = modes.all_tweaks(self.backup)
        self.pages: Dict[str, Page] = {}
        self.active_mode: Optional[str] = None
        self.states: Dict[str, Optional[bool]] = {}
        self.current = ""
        self._logo: Optional[tk.PhotoImage] = None

        self._build()
        self.bind_all("<MouseWheel>", self._on_wheel)
        self.after(80, self._pump)
        self.after(600, self._tick)

        self.deiconify()
        self.update_idletasks()
        self.show("mode")

        self.log("Marshall IX9 siap. Semua perubahan dicatat di sini dan bisa dikembalikan.", "info")
        if wu.IS_WIN and not wu.is_admin():
            self.log("Belum berjalan sebagai Administrator: sebagian pengaturan akan dilewati.", "warn")
        self.run_task("baca status", self.snapshot, self.on_snapshot, quiet=True)

    # ------------------------------------------------------------------ window setup
    def _size_window(self) -> None:
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width = min(T.px(960), screen_w - T.px(60))
        height = min(T.px(640), screen_h - T.px(90))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(T.px(820), width), min(T.px(560), height))

    def _set_icon(self) -> None:
        icon = resource_path("assets/icon.ico")
        if wu.IS_WIN and os.path.exists(icon):
            try:
                self.iconbitmap(icon)
            except tk.TclError:
                pass

    def _style_scrollbars(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
            for name, thumb, trough in (("Ix9", "#E8D3A0", T.CARD), ("Ix9Dark", "#2E3B4A", T.TERM_BG)):
                sid = f"{name}.Vertical.TScrollbar"
                style.configure(sid, background=thumb, troughcolor=trough, bordercolor=trough, lightcolor=thumb,
                                darkcolor=thumb, arrowcolor=thumb, relief="flat")
                style.map(sid, background=[("active", T.shade(thumb, 0.9)), ("pressed", T.shade(thumb, 0.8))])
                style.layout(sid, [("Vertical.Scrollbar.trough", {
                    "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        except tk.TclError:
            pass  # the default scrollbar look is fine

    def _load_logo(self) -> Optional[tk.PhotoImage]:
        wanted = T.px(64)
        best = None
        for size in (48, 64, 96, 128, 192, 256, 384):
            path = resource_path(f"assets/logo_{size}.png")
            if os.path.exists(path) and (best is None or abs(size - wanted) < abs(best[0] - wanted)):
                best = (size, path)
        if best is None:
            return None
        try:
            return tk.PhotoImage(file=best[1])
        except tk.TclError:
            return None

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        self.backdrop = Backdrop(self, T.LOOKS["amber"])
        self.backdrop.pack(fill="both", expand=True)
        self._logo = self._load_logo()
        self.nav = Nav(self.backdrop, self.PAGES, "log", self.show, self._logo, "Marshall IX9",
                       f"PC optimizer v{__version__}")

        card = self.backdrop.card
        header = tk.Frame(card, bg=T.CARD)
        header.pack(fill="x", padx=T.px(22), pady=(T.px(18), T.px(10)))
        titles = tk.Frame(header, bg=T.CARD)
        titles.pack(side="left")
        self.title_label = tk.Label(titles, text="", font="ix9.title", fg=T.INK, bg=T.CARD, anchor="w")
        self.title_label.pack(anchor="w")
        self.blurb_label = tk.Label(titles, text="", font="ix9.small", fg=T.MUTED, bg=T.CARD, anchor="w")
        self.blurb_label.pack(anchor="w")
        status = tk.Frame(header, bg=T.CARD)
        status.pack(side="right", anchor="n")
        self.lamp = Lamp(status, bg=T.CARD)
        self.lamp.pack(side="left", padx=(0, T.px(8)))
        self.status_label = tk.Label(status, text="Siap", font="ix9.bodyb", fg=T.INK, bg=T.CARD)
        self.status_label.pack(side="left")

        if wu.IS_WIN and not wu.is_admin():
            banner = tk.Frame(card, bg=T.SOFT)
            banner.pack(fill="x", padx=T.px(22), pady=(0, T.px(10)))
            tk.Label(banner, text="Belum Administrator, jadi sebagian pengaturan akan dilewati.", font="ix9.body",
                     fg=T.INK, bg=T.SOFT).pack(side="left", padx=T.px(14), pady=T.px(8))
            Btn(banner, "Jalankan sebagai admin", self.relaunch_as_admin).pack(side="right", padx=T.px(8), pady=T.px(6))

        content = tk.Frame(card, bg=T.CARD)
        content.pack(fill="both", expand=True, padx=T.px(22), pady=(0, T.px(18)))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        for key, cls in (("mode", ModePage), ("cleaner", CleanerPage), ("apps", AppsPage),
                         ("safety", SafetyPage), ("log", LogPage)):
            page = cls(content, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

    @property
    def console(self):
        return self.pages["log"].view  # type: ignore[attr-defined]

    def show(self, key: str) -> None:
        page = self.pages[key]
        page.tkraise()
        self.current = key
        self.nav.set_active(key)
        self.title_label.configure(text=page.title)
        self.blurb_label.configure(text=page.blurb)
        page.on_show()

    def set_look(self, mode_id: Optional[str]) -> None:
        """Give the window the colours of a mode (amber when no mode is active)."""
        look = T.LOOKS[modes.MODES[mode_id].look if mode_id in modes.MODES else "amber"]
        if look is self.backdrop.look:
            return
        self.backdrop.set_look(look)
        self.nav.apply_look(look)

    # ------------------------------------------------------------------ threads and messages
    def log(self, message: str, level: str = "info") -> None:
        """Safe to call from any thread."""
        self.queue.put(("log", message, level))

    def run_task(self, label: str, fn: Callable[[], object], done: Optional[Callable[[object], None]] = None,
                 quiet: bool = False) -> bool:
        """Run `fn` in a worker thread, then call `done(result)` on the UI thread. False if already busy."""
        if self.busy:
            if not quiet:
                self.log("Masih ada proses yang berjalan, tunggu sebentar.", "warn")
            return False
        self.busy = True
        self._set_working(True)

        def work() -> None:
            result = None
            try:
                result = fn()
            except Exception as exc:
                self.log(f"Error pada '{label}': {exc}", "err")
                write_error_log(traceback.format_exc())
            self.queue.put(("done", done, result))

        threading.Thread(target=work, daemon=True).start()
        return True

    def _pump(self) -> None:
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.console.add(item[1], item[2])
                elif kind == "call":
                    item[1]()
                elif kind == "done":
                    self.busy = False
                    self._set_working(False)
                    if item[1] is not None:
                        try:
                            item[1](item[2])
                        except Exception as exc:
                            self.console.add(f"Error di tampilan: {exc}", "err")
                            write_error_log(traceback.format_exc())
        except queue.Empty:
            pass
        self.after(80, self._pump)

    def _set_working(self, working: bool) -> None:
        self.lamp.set(T.ORANGE if working else T.GREEN)
        self.status_label.configure(text="Bekerja..." if working else "Siap")

    def report_callback_exception(self, exc, val, tb) -> None:  # Tk calls this for errors inside callbacks
        text = "".join(traceback.format_exception(exc, val, tb))
        write_error_log(text)
        try:
            self.console.add(f"Error di tampilan: {val}", "err")
        except Exception:
            pass

    def _on_wheel(self, event) -> None:
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        while widget is not None:
            if isinstance(widget, ScrollFrame):
                widget.wheel(event.delta)
                return
            widget = getattr(widget, "master", None)

    # ------------------------------------------------------------------ state
    def snapshot(self) -> Dict[str, Optional[bool]]:
        return tw.snapshot(self.tweaks)

    def on_snapshot(self, states) -> None:
        if not states:
            return
        self.states = states
        self.active_mode = modes.detect_mode(states, modes.recall(self.backup))
        self.set_look(self.active_mode)
        for page in self.pages.values():
            page.on_states(states)

    def _tick(self) -> None:
        try:
            if psutil is not None:
                self.pages["mode"].update_live(  # type: ignore[attr-defined]
                    psutil.cpu_percent(interval=None), psutil.virtual_memory().percent, power.on_ac())
        except Exception:
            pass
        self.after(1000, self._tick)

    # ------------------------------------------------------------------ actions used by the pages
    def confirm(self, title: str, message: str) -> bool:
        return bool(messagebox.askyesno(title, message, parent=self))

    def set_mode(self, mode_id: str) -> bool:
        """One click: the background takes the mode's colour at once, the settings follow in the background."""
        if self.busy:
            self.log("Masih ada proses yang berjalan, tunggu sebentar.", "warn")
            return False
        mode = modes.MODES[mode_id]
        self.set_look(mode_id)
        self.pages["mode"].show_result(f"Memasang mode {mode.title}...")  # type: ignore[attr-defined]

        def job():
            results = modes.apply_mode(self.tweaks, mode_id, self.log)
            modes.remember(self.backup, mode_id)
            return self.snapshot(), modes.summary(mode_id, results)

        return self.run_task(f"mode {mode.title}", job, self._after_mode)

    def reset_modes(self) -> bool:
        if self.busy:
            self.log("Masih ada proses yang berjalan, tunggu sebentar.", "warn")
            return False
        if not self.confirm("Kembalikan ke awal", "Kembalikan semua pengaturan yang diubah Marshall IX9 ke nilai awalnya?"):
            return False

        def job():
            modes.reset_all(self.tweaks, self.log)
            modes.remember(self.backup, None)
            return self.snapshot(), "Semua pengaturan dikembalikan ke awal."

        return self.run_task("kembalikan ke awal", job, self._after_mode)

    def _after_mode(self, result) -> None:
        if not result:
            return
        states, text = result
        self.on_snapshot(states)
        self.pages["mode"].show_result(text)  # type: ignore[attr-defined]

    def make_restore_point(self) -> None:
        self.run_task("restore point", lambda: tw.create_restore_point(self.log))

    def flush_dns(self) -> None:
        self.run_task("flush dns", lambda: tw.flush_dns(self.log))

    def open_target(self, target: str) -> None:
        try:
            os.startfile(target)  # type: ignore[attr-defined]  # Windows only
        except (AttributeError, OSError) as exc:
            self.log(f"Tidak bisa membuka {target}: {exc}", "warn")

    def relaunch_as_admin(self) -> None:
        if not wu.IS_WIN:
            return
        try:
            if getattr(sys, "frozen", False):
                exe, params = sys.executable, ""
            else:
                exe, params = sys.executable, f'"{os.path.abspath(sys.argv[0])}"'
            if ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1) > 32:
                self.destroy()
        except Exception as exc:
            self.log(f"Gagal meminta hak Administrator: {exc}", "err")


def run() -> None:
    try:
        App().mainloop()
    except Exception:
        text = traceback.format_exc()
        path = write_error_log(text)
        if wu.IS_WIN:
            try:
                ctypes.windll.user32.MessageBoxW(0, f"Marshall IX9 gagal dijalankan.\n\n{text[-700:]}\n\nLog: {path}", APP_NAME, 0x10)
            except Exception:
                pass
        raise
