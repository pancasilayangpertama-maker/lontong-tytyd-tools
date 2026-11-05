"""Modes: one click applies a whole package of tweaks (Santai, Balance, Gaming).

Santai  = Game Mode, Game Bar recording off, transparency off.
Balance = Santai + game scheduler priority + pointer precision off.
Gaming  = every tweak, plus the highest game priority, all CPU cores unparked and the GPU asked to run flat out.

Switching modes first undoes what this app turned on and the new mode does not want, so modes never pile up.
Only tweaks that have a backup are ever undone, so a setting you changed yourself is never touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import power
from . import tweaks as tw
from .winutil import REG_DWORD, REG_SZ, BackupStore

# Extra power-setting GUIDs (all are "plugged in" values of the active power plan; unsupported ones are skipped)
CPMINCORES = "0cc5b647-c1df-4637-891a-dec35c318583"          # core parking: minimum cores
CPMINCORES_CLASS1 = "0cc5b647-c1df-4637-891a-dec35c318584"   # the same, for the second core class (hybrid CPUs)
SUB_INTEL_GRAPHICS = "44f3beca-a7c0-460e-9df2-bb8b99e0cba6"
INTEL_GRAPHICS_POWER_PLAN = "3619c3f2-afb2-4afc-b0e9-e7fef372de36"  # 0 battery, 1 balanced, 2 maximum performance
SUB_AMD_GRAPHICS = "e276e160-7cb0-43c6-b20b-73f5dce39954"
AMD_SWITCHABLE_GRAPHICS = "a1662ab2-9d34-4e53-ba8b-2639b9e20857"    # 3 = maximum performance


class CpuUnpark(tw.PowerSettingsTweak):
    id = "cpu_unpark"
    title = "Semua core CPU aktif (unpark)"
    desc = ("Windows biasanya 'memarkir' sebagian core saat beban ringan. Di sini semua core dibiarkan siap kerja, "
            "jadi lonjakan beban di game tidak menunggu core dibangunkan.")
    impact = 3
    settings = (
        ("Core parking: minimum core 100%", power.SUB_PROCESSOR, CPMINCORES, 100),
        ("Core parking kelas 2: minimum core 100%", power.SUB_PROCESSOR, CPMINCORES_CLASS1, 100),
    )


class GpuBoost(tw.PowerSettingsTweak):
    id = "gpu_boost"
    title = "GPU / iGPU kerja maksimal"
    desc = ("Driver grafis Intel / AMD diminta memakai mode performa tertinggi saat dicas. "
            "Yang tidak didukung di laptopmu dilewati otomatis.")
    impact = 3
    settings = (
        ("Intel Graphics Power Plan: Maximum Performance", SUB_INTEL_GRAPHICS, INTEL_GRAPHICS_POWER_PLAN, 2),
        ("AMD Switchable Graphics: Maximum performance", SUB_AMD_GRAPHICS, AMD_SWITCHABLE_GRAPHICS, 3),
    )


class MmcssHigh(tw.Mmcss):
    id = "mmcss_high"
    title = "Prioritas game tertinggi (MMCSS)"
    desc = ("Tugas 'Games' diberi prioritas tertinggi (8) di scheduler Windows, plus prioritas GPU maksimal "
            "dan tanpa throttling jaringan.")
    impact = 2
    _p = tw.Mmcss._profile
    values = (
        tw.RegSet("HKLM", _p, "NetworkThrottlingIndex", 0xFFFFFFFF, REG_DWORD, 10),
        tw.RegSet("HKLM", _p, "SystemResponsiveness", 0, REG_DWORD, 20),
        tw.RegSet("HKLM", _p + r"\Tasks\Games", "Priority", 8, REG_DWORD, 2),
        tw.RegSet("HKLM", _p + r"\Tasks\Games", "GPU Priority", 8, REG_DWORD, 8),
        tw.RegSet("HKLM", _p + r"\Tasks\Games", "Scheduling Category", "High", REG_SZ, "Medium"),
        tw.RegSet("HKLM", _p + r"\Tasks\Games", "SFIO Priority", "High", REG_SZ, "Normal"),
    )


def all_tweaks(backup: BackupStore) -> List[tw.Tweak]:
    return tw.build_tweaks(backup) + [CpuUnpark(backup), GpuBoost(backup), MmcssHigh(backup)]


@dataclass(frozen=True)
class Mode:
    id: str
    title: str
    tagline: str
    look: str                 # which colour look the window takes: "blue", "amber" or "red"
    tweak_ids: Tuple[str, ...]
    bullets: Tuple[str, ...]
    note: str = ""


SANTAI = ("game_mode", "game_dvr", "transparency")
BALANCE = SANTAI + ("mmcss", "pointer")
GAMING = ("power_mode", "cpu_cooling", "device_power", "game_mode", "game_dvr", "transparency",
          "mmcss_high", "pointer", "cpu_unpark", "gpu_boost")

ORDER = ("santai", "balance", "gaming")
MODES: Dict[str, Mode] = {
    "santai": Mode(
        "santai", "Santai", "Ringan untuk pemakaian harian.", "blue", SANTAI,
        ("Game Mode aktif", "Perekaman Game Bar mati", "Efek transparan mati")),
    "balance": Mode(
        "balance", "Balance", "Seimbang: prioritas game naik sedikit, tetap adem.", "amber", BALANCE,
        ("Semua milik Santai", "Prioritas scheduler game", "Pointer precision mati")),
    "gaming": Mode(
        "gaming", "Gaming", "Maksimal untuk main. Paling kencang, paling panas.", "red", GAMING,
        ("Semua milik Balance", "Mode daya Best performance", "CPU boost agresif, kipas lebih dulu",
         "Semua core CPU aktif (unpark)", "GPU / iGPU kerja maksimal", "Prioritas game tertinggi",
         "Tanpa hemat daya USB, PCIe, Wi-Fi"),
        "Hanya berlaku saat dicas. Laptop bisa lebih panas dan kipas lebih kencang."),
}

_KEY = "mode|current"


def remember(backup: BackupStore, mode_id: Optional[str]) -> None:
    backup.pop(_KEY)
    if mode_id:
        backup.put_if_absent(_KEY, {"id": mode_id})
    backup.save()


def recall(backup: BackupStore) -> Optional[str]:
    rec = backup.get(_KEY)
    return rec.get("id") if rec else None


def apply_mode(tweaks: List[tw.Tweak], mode_id: str, log) -> Dict[str, bool]:
    mode = MODES[mode_id]
    wanted = set(mode.tweak_ids)
    by_id = {t.id: t for t in tweaks}
    log(f"Mode {mode.title}: mulai", "info")
    for tweak in tweaks:  # 1) switch off what this app turned on and the new mode does not want
        if tweak.id not in wanted and tweak.has_backup():
            try:
                tweak.undo(log)
            except Exception as exc:
                log(f"{tweak.title}: gagal dikembalikan: {exc}", "err")
    results: Dict[str, bool] = {}
    for tweak_id in mode.tweak_ids:  # 2) switch on everything the mode wants
        tweak = by_id.get(tweak_id)
        if tweak is None:
            continue
        log(f"> {tweak.title}", "info")
        try:
            results[tweak_id] = bool(tweak.apply(log))
        except Exception as exc:  # one failing tweak must not stop the others
            results[tweak_id] = False
            log(f"{tweak.title}: error tak terduga: {exc}", "err")
    done = sum(1 for ok in results.values() if ok)
    log(f"Mode {mode.title}: {done} dari {len(results)} pengaturan terpasang", "ok" if done == len(results) else "warn")
    return results


def reset_all(tweaks: List[tw.Tweak], log) -> int:
    """Undo everything this app changed. Settings it never touched are left alone."""
    restored = 0
    for tweak in tweaks:
        if tweak.has_backup():
            try:
                if tweak.undo(log):
                    restored += 1
            except Exception as exc:
                log(f"{tweak.title}: gagal dikembalikan: {exc}", "err")
    log(f"Kembali ke awal: {restored} pengaturan dipulihkan", "ok")
    return restored


def summary(mode_id: str, results: Dict[str, bool]) -> str:
    mode = MODES[mode_id]
    done = sum(1 for ok in results.values() if ok)
    text = f"Mode {mode.title}: {done} dari {len(results)} pengaturan terpasang."
    if done < len(results):
        text += " Sisanya dilewati (tidak didukung di laptop ini, atau butuh Administrator / charger). Detailnya ada di Log."
    return text


def detect_mode(states: Dict[str, Optional[bool]], current: Optional[str] = None) -> Optional[str]:
    """Which mode is on right now. `current` is the mode this app applied last (a partly applied mode still counts)."""

    def share(mode_id: str) -> float:
        ids = MODES[mode_id].tweak_ids
        if any(i not in states for i in ids):
            return 0.0  # an incomplete snapshot cannot prove a mode is on
        known = [states[i] for i in ids if states[i] is not None]  # None = unsupported here, not counted
        return (sum(1 for s in known if s) / len(known)) if known else 0.0

    if current in MODES and share(current) >= 0.5:
        return current
    for mode_id in ("gaming", "balance", "santai"):
        ids = MODES[mode_id].tweak_ids
        if share(mode_id) == 1.0 and any(states.get(i) for i in ids):
            return mode_id
    return None
