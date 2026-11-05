"""The pages of the window. Each page talks to the App only through a few small methods."""
from __future__ import annotations

import tkinter as tk
from typing import Dict, Optional, Tuple

from ..core import cleaner, modes, processes, startup
from ..core import winutil as wu
from . import theme as T
from .widgets import AutoLabel, Btn, LogView, ScrollFrame, Switch


class Page(tk.Frame):
    title = ""
    blurb = ""

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, bg=T.CARD)
        self.app = app

    def on_show(self) -> None:
        """Called every time the page becomes visible."""

    def on_states(self, states: Dict[str, Optional[bool]]) -> None:
        """Called whenever the tweak states were re-read."""


class ScrollPage(Page):
    """A page that scrolls when the window is too short, so nothing is ever cut off."""

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        self.scroll = ScrollFrame(self, bg=T.CARD)
        self.scroll.pack(fill="both", expand=True)
        self.body = self.scroll.inner


def _box(master: tk.Misc) -> tk.Frame:
    return tk.Frame(master, bg=T.PANEL, highlightthickness=1, highlightbackground=T.LINE, highlightcolor=T.LINE, bd=0)


def _check(master: tk.Misc, text: str, variable: tk.BooleanVar) -> tk.Checkbutton:
    return tk.Checkbutton(master, text=text, variable=variable, font="ix9.small", fg=T.MUTED, bg=T.CARD,
                          activebackground=T.CARD, activeforeground=T.INK, selectcolor=T.PANEL,
                          highlightthickness=0, bd=0, anchor="w", cursor="hand2")


# =============================================================================== mode


class ModePage(ScrollPage):
    title = "Mode performa"
    blurb = "Pilih satu paket. Pengaturannya dipasang otomatis dan bisa dikembalikan."

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        body = self.body
        for column in range(3):
            body.columnconfigure(column, weight=1, uniform="mode")
        self.cards: Dict[str, dict] = {}
        for column, mode_id in enumerate(modes.ORDER):
            self.cards[mode_id] = self._card(body, column, modes.MODES[mode_id])
        foot = tk.Frame(body, bg=T.CARD)
        foot.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(T.px(16), 0))
        Btn(foot, "Kembalikan ke awal", app.reset_modes, kind="soft").pack(side="left")
        self.note = AutoLabel(foot, text="Belum ada mode aktif.", font="ix9.body", fg=T.MUTED, bg=T.CARD)
        self.note.pack(side="left", fill="x", expand=True, padx=(T.px(14), 0))
        self.live = tk.Label(body, text="", font="ix9.small", fg=T.MUTED, bg=T.CARD, anchor="w")
        self.live.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(T.px(12), 0))

    def _card(self, parent: tk.Misc, column: int, mode: modes.Mode) -> dict:
        look = T.LOOKS[mode.look]
        card = _box(parent)
        card.configure(highlightthickness=2)
        card.grid(row=0, column=column, sticky="nsew",
                  padx=(0 if column == 0 else T.px(7), 0 if column == 2 else T.px(7)))
        tk.Frame(card, bg=look.accent, height=T.px(6)).pack(fill="x")
        button = Btn(card, "Aktifkan", lambda m=mode.id: self.app.set_mode(m), color=look.accent)
        button.pack(side="bottom", fill="x", padx=T.px(16), pady=(T.px(12), T.px(16)))
        tk.Label(card, text=mode.title, font="ix9.h1", fg=T.INK, bg=T.PANEL, anchor="w").pack(
            fill="x", padx=T.px(16), pady=(T.px(14), 0))
        badge = tk.Label(card, text="", font="ix9.small", fg=look.accent, bg=T.PANEL, anchor="w")
        badge.pack(fill="x", padx=T.px(16))
        AutoLabel(card, text=mode.tagline, font="ix9.small", fg=T.MUTED, bg=T.PANEL).pack(
            fill="x", padx=T.px(16), pady=(T.px(2), T.px(8)))
        for line in mode.bullets:
            AutoLabel(card, text="\u2022  " + line, font="ix9.body", fg=T.INK, bg=T.PANEL).pack(
                fill="x", padx=T.px(16), pady=(0, T.px(3)))
        if mode.note:
            AutoLabel(card, text=mode.note, font="ix9.small", fg=T.ORANGE, bg=T.PANEL).pack(
                fill="x", padx=T.px(16), pady=(T.px(6), 0))
        return {"frame": card, "button": button, "badge": badge, "look": look}

    def set_active(self, mode_id: Optional[str]) -> None:
        for key, card in self.cards.items():
            active = key == mode_id
            color = card["look"].accent if active else T.LINE
            card["frame"].configure(highlightbackground=color, highlightcolor=color)
            card["badge"].configure(text="\u25CF Aktif" if active else "")
            card["button"].set_text("Terapkan ulang" if active else "Aktifkan")
        if mode_id is None:
            self.note.configure(text="Belum ada mode aktif.")
        elif mode_id in modes.MODES:
            self.note.configure(text=f"Mode {modes.MODES[mode_id].title} aktif.")

    def show_result(self, text: str) -> None:
        self.note.configure(text=text)

    def update_live(self, cpu: float, ram: float, plugged: Optional[bool]) -> None:
        power = "Charger tersambung" if plugged else ("Memakai baterai" if plugged is False else "")
        self.live.configure(text=f"CPU {cpu:.0f}%     RAM {ram:.0f}%     {power}".rstrip())

    def on_states(self, states: Dict[str, Optional[bool]]) -> None:
        self.set_active(self.app.active_mode)


# =============================================================================== cleaner


class CleanerPage(ScrollPage):
    title = "Pembersih"
    blurb = "Hapus file sampah yang aman dihapus. Pindai dulu, lalu bersihkan."

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        box = _box(self.body)
        box.pack(fill="x")
        self.checks: Dict[str, tk.BooleanVar] = {}
        self.sizes: Dict[str, tk.Label] = {}
        for index, cat in enumerate(cleaner.CATEGORIES):
            if index:
                tk.Frame(box, bg=T.LINE, height=1).pack(fill="x")
            row = tk.Frame(box, bg=T.PANEL)
            row.pack(fill="x")
            row.columnconfigure(1, weight=1)
            var = tk.BooleanVar(master=self, value=True)
            self.checks[cat.id] = var
            tk.Checkbutton(row, variable=var, bg=T.PANEL, activebackground=T.PANEL, selectcolor=T.PANEL,
                           fg=T.ORANGE, activeforeground=T.ORANGE, highlightthickness=0, bd=0, cursor="hand2").grid(
                row=0, column=0, rowspan=2, padx=(T.px(14), T.px(4)))
            tk.Label(row, text=cat.title, font="ix9.h2", fg=T.INK, bg=T.PANEL, anchor="w").grid(
                row=0, column=1, sticky="ew", pady=(T.px(12), 0))
            AutoLabel(row, text=cat.desc, font="ix9.small", fg=T.MUTED, bg=T.PANEL).grid(
                row=1, column=1, sticky="ew", pady=(0, T.px(12)))
            size = tk.Label(row, text="belum dipindai", font="ix9.small", fg=T.MUTED, bg=T.PANEL, anchor="e")
            size.grid(row=0, column=2, rowspan=2, padx=T.px(16))
            self.sizes[cat.id] = size

        bar = tk.Frame(self.body, bg=T.CARD)
        bar.pack(fill="x", pady=(T.px(14), 0))
        Btn(bar, "Pindai", self.scan, kind="soft").pack(side="left")
        Btn(bar, "Bersihkan yang dicentang", self.clean).pack(side="left", padx=(T.px(8), 0))
        self.recent = tk.BooleanVar(master=self, value=False)
        _check(bar, "Termasuk file yang lebih baru dari 24 jam (tidak disarankan)", self.recent).pack(
            side="left", padx=(T.px(16), 0))
        self.summary = tk.Label(self.body, text="", font="ix9.body", fg=T.MUTED, bg=T.CARD, anchor="w")
        self.summary.pack(fill="x", pady=(T.px(14), 0))

    def scan(self) -> None:
        include = bool(self.recent.get())

        def job():
            return {cat.id: cleaner.scan(cat, include) for cat in cleaner.CATEGORIES}

        self.app.run_task("pindai", job, self._show)

    def clean(self) -> None:
        chosen = [cat for cat in cleaner.CATEGORIES if self.checks[cat.id].get()]
        if not chosen:
            self.app.log("Belum ada kategori yang dicentang", "warn")
            return
        if not self.app.confirm("Bersihkan", "Hapus file di kategori yang dicentang?\n\n"
                                "File yang dihapus tidak bisa dikembalikan (Recycle Bin dikosongkan permanen)."):
            return
        include = bool(self.recent.get())

        def job():
            total = 0
            for cat in chosen:
                freed, deleted, skipped = cleaner.clean(cat, include)
                total += freed
                self.app.log(f"{cat.title}: {cleaner.format_size(freed)} dibersihkan ({deleted} file, {skipped} dilewati karena sedang dipakai)",
                             "ok" if (deleted or freed) else "dim")
            self.app.log(f"Total ruang yang kembali: {cleaner.format_size(total)}", "ok")
            return {cat.id: cleaner.scan(cat, include) for cat in cleaner.CATEGORIES}

        self.app.run_task("bersihkan", job, self._show)

    def _show(self, result: Optional[Dict[str, Tuple[int, int]]]) -> None:
        if not result:
            return
        total = 0
        for cat in cleaner.CATEGORIES:
            size, files = result.get(cat.id, (0, 0))
            total += size
            text = "kosong" if size == 0 and files == 0 else f"{cleaner.format_size(size)} ({files} file)"
            self.sizes[cat.id].configure(text=text, fg=T.INK if size else T.MUTED)
        self.summary.configure(text=f"Bisa dibersihkan sekarang: {cleaner.format_size(total)}", fg=T.INK if total else T.MUTED)
        self.app.log(f"Pindai selesai: {cleaner.format_size(total)} bisa dibersihkan", "info")


# =============================================================================== apps + startup


class AppsPage(Page):
    title = "Aplikasi"
    blurb = "Tutup aplikasi berat sebelum main dan rapikan startup Windows."

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        self._attempts = 0
        top = tk.Frame(self, bg=T.CARD)
        top.pack(fill="x", pady=(0, T.px(8)))
        Btn(top, "Segarkan", self.refresh, kind="soft").pack(side="right")
        AutoLabel(top, text="Hanya aplikasi milikmu yang tampil. Proses sistem Windows tidak pernah muncul di sini.",
                  font="ix9.small", fg=T.MUTED, bg=T.CARD).pack(side="left", fill="x", expand=True)
        columns = tk.Frame(self, bg=T.CARD)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1, uniform="cols")
        columns.columnconfigure(1, weight=1, uniform="cols")
        columns.rowconfigure(0, weight=1)
        self.apps = self._column(columns, 0, "Aplikasi berjalan, terbesar dulu")
        self.startup = self._column(columns, 1, "Aplikasi startup Windows")

    def _column(self, parent: tk.Misc, column: int, title: str) -> ScrollFrame:
        box = _box(parent)
        box.grid(row=0, column=column, sticky="nsew",
                 padx=(0 if column == 0 else T.px(6), 0 if column == 1 else T.px(6)))
        tk.Label(box, text=title, font="ix9.h2", fg=T.INK, bg=T.PANEL).pack(anchor="w", padx=T.px(14), pady=(T.px(12), T.px(8)))
        scroll = ScrollFrame(box, bg=T.PANEL)
        scroll.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        return scroll

    def on_show(self) -> None:
        self._attempts = 0
        self._refresh_when_free()

    def _refresh_when_free(self) -> None:
        """Load the lists; if another job is still running, try again shortly."""
        if not self.winfo_exists():
            return
        if not self.refresh(quiet=True) and self._attempts < 12:
            self._attempts += 1
            self.after(300, self._refresh_when_free)

    def refresh(self, quiet: bool = False) -> bool:
        def job():
            return processes.list_user_apps(), startup.list_items()

        return self.app.run_task("segarkan daftar", job, self._fill, quiet=quiet)

    def _fill(self, result) -> None:
        if not result:
            return
        apps, items = result
        self.apps.clear()
        if not apps:
            tk.Label(self.apps.inner, text="Tidak ada aplikasi yang bisa ditampilkan.", font="ix9.body", fg=T.MUTED,
                     bg=T.PANEL).pack(padx=T.px(14), pady=T.px(14), anchor="w")
        for row in apps:
            self._app_row(row)
        self.startup.clear()
        if not items:
            tk.Label(self.startup.inner, text="Tidak ada aplikasi startup yang bisa ditampilkan.", font="ix9.body",
                     fg=T.MUTED, bg=T.PANEL).pack(padx=T.px(14), pady=T.px(14), anchor="w")
        for item in items:
            self._startup_row(item)

    def _app_row(self, row: processes.AppRow) -> None:
        inner = self.apps.inner
        frame = tk.Frame(inner, bg=T.PANEL)
        frame.pack(fill="x")
        frame.columnconfigure(0, weight=1)
        text = tk.Frame(frame, bg=T.PANEL)
        text.grid(row=0, column=0, sticky="ew", padx=T.px(14), pady=T.px(8))
        tk.Label(text, text=row.name, font="ix9.bodyb", fg=T.INK, bg=T.PANEL, anchor="w").pack(fill="x")
        tk.Label(text, text=f"{len(row.pids)} proses, {cleaner.format_size(row.rss)}", font="ix9.small", fg=T.MUTED,
                 bg=T.PANEL, anchor="w").pack(fill="x")
        buttons = tk.Frame(frame, bg=T.PANEL)
        buttons.grid(row=0, column=1, padx=(0, T.px(12)))
        Btn(buttons, "Normalkan" if row.high else "Prioritas", lambda r=row: self._priority(r), kind="soft").pack(side="left")
        Btn(buttons, "Tutup", lambda r=row: self._close(r), color=T.DANGER).pack(side="left", padx=(T.px(6), 0))
        tk.Frame(inner, bg=T.LINE, height=1).pack(fill="x")

    def _close(self, row: processes.AppRow) -> None:
        if not self.app.confirm("Tutup aplikasi", f"Tutup {row.name} ({len(row.pids)} proses)?\n\nPekerjaan yang belum disimpan di aplikasi itu akan hilang."):
            return

        def job():
            closed = processes.close_app(list(row.pids))
            self.app.log(f"{row.name}: {closed} proses ditutup", "ok" if closed else "warn")
            return processes.list_user_apps(), startup.list_items()

        self.app.run_task(f"tutup {row.name}", job, self._fill)

    def _priority(self, row: processes.AppRow) -> None:
        make_high = not row.high

        def job():
            changed = processes.set_priority(list(row.pids), make_high)
            state = "Prioritas tinggi" if make_high else "Prioritas normal"
            self.app.log(f"{row.name}: {state} untuk {changed} proses (kembali normal kalau aplikasinya ditutup)", "ok" if changed else "warn")
            return processes.list_user_apps(), startup.list_items()

        self.app.run_task(f"prioritas {row.name}", job, self._fill)

    def _startup_row(self, item: startup.StartupItem) -> None:
        inner = self.startup.inner
        frame = tk.Frame(inner, bg=T.PANEL)
        frame.pack(fill="x")
        frame.columnconfigure(0, weight=1)
        text = tk.Frame(frame, bg=T.PANEL)
        text.grid(row=0, column=0, sticky="ew", padx=T.px(14), pady=T.px(8))
        tk.Label(text, text=item.name, font="ix9.bodyb", fg=T.INK, bg=T.PANEL, anchor="w").pack(fill="x")
        tk.Label(text, text=item.source, font="ix9.small", fg=T.MUTED, bg=T.PANEL, anchor="w").pack(fill="x")
        switch = Switch(frame, command=lambda want, it=item: self._toggle_startup(it, want), bg=T.PANEL)
        switch.set(item.enabled)
        switch.grid(row=0, column=1, padx=T.px(14))
        tk.Frame(inner, bg=T.LINE, height=1).pack(fill="x")

    def _toggle_startup(self, item: startup.StartupItem, want: bool) -> bool:
        def job():
            ok = startup.set_enabled(item, want)
            self.app.log(f"Startup {item.name}: {'dinyalakan' if want else 'dimatikan'}" if ok else f"Startup {item.name}: gagal diubah",
                         "ok" if ok else "err")
            return ok

        return self.app.run_task(f"startup {item.name}", job, lambda ok: None if ok else self.refresh(quiet=True))


# =============================================================================== safety


class SafetyPage(ScrollPage):
    title = "Keamanan"
    blurb = "Apa yang dilakukan Marshall IX9, dan apa yang tidak pernah dilakukannya."

    POINTS = (
        ("Tanpa internet", "Kodenya tidak memakai modul jaringan apa pun. Ada tes otomatis yang gagal kalau ada yang menambahkannya."),
        ("Semua tercatat", "Setiap perubahan muncul di halaman Log, dan nilai asli disimpan ke backup.json sebelum diubah."),
        ("Bisa dikembalikan", "Tombol 'Kembalikan ke awal' memulihkan nilai awal, bahkan setelah komputer di-restart. Pengaturan yang kamu ubah sendiri tidak disentuh."),
        ("Cakupan sempit", "Hanya kunci registry dan pengaturan daya yang tertulis di Log, folder Temp, dan aplikasi yang kamu klik sendiri."),
        ("Tanpa fitur palsu", "Tidak ada 'RAM cleaner' atau 'GPU overclock'. Tombol seperti itu tidak membantu, kadang malah memperlambat."),
    )

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        box = _box(self.body)
        box.pack(fill="x")
        for index, (head, text) in enumerate(self.POINTS):
            if index:
                tk.Frame(box, bg=T.LINE, height=1).pack(fill="x")
            row = tk.Frame(box, bg=T.PANEL)
            row.pack(fill="x", padx=T.px(18), pady=T.px(11))
            tk.Label(row, text=head, font="ix9.h2", fg=T.ORANGE, bg=T.PANEL, anchor="w").pack(fill="x")
            AutoLabel(row, text=text, font="ix9.body", fg=T.MUTED, bg=T.PANEL).pack(fill="x", pady=(T.px(2), 0))
        tools = tk.Frame(self.body, bg=T.CARD)
        tools.pack(fill="x", pady=(T.px(14), 0))
        Btn(tools, "Buat restore point", app.make_restore_point).pack(side="left")
        Btn(tools, "Buka folder backup", lambda: app.open_target(wu.data_dir()), kind="soft").pack(side="left", padx=(T.px(8), 0))
        Btn(tools, "Pengaturan daya Windows", lambda: app.open_target("ms-settings:powersleep"), kind="soft").pack(side="left", padx=(T.px(8), 0))
        Btn(tools, "Bersihkan cache DNS", app.flush_dns, kind="soft").pack(side="left", padx=(T.px(8), 0))
        self.where = tk.Label(self.body, text="", font="ix9.small", fg=T.MUTED, bg=T.CARD, anchor="w")
        self.where.pack(fill="x", pady=(T.px(12), 0))

    def on_show(self) -> None:
        self.where.configure(text=f"Backup nilai asli: {wu.data_dir()}")


# =============================================================================== log


class LogPage(Page):
    title = "Activity Log"
    blurb = "Catatan semua yang dilakukan aplikasi, urut waktu."

    def __init__(self, master: tk.Misc, app) -> None:
        super().__init__(master, app)
        bar = tk.Frame(self, bg=T.CARD)
        bar.pack(side="bottom", fill="x", pady=(T.px(10), 0))
        self.view = LogView(self)
        self.view.pack(fill="both", expand=True)
        Btn(bar, "Bersihkan tampilan", self.view.clear, kind="soft").pack(side="left")
        Btn(bar, "Buka folder log", lambda: app.open_target(wu.data_dir()), kind="soft").pack(side="left", padx=(T.px(8), 0))
