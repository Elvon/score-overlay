# SPDX-License-Identifier: GPL-3.0-or-later
"""Borderless, always-on-top overlay window with clock and scores."""
import ctypes
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox
from datetime import datetime, timezone
from pathlib import Path

from overlay import __version__, config, single_instance, updater
from overlay.sound import play_goal_sound
from overlay.goals import GoalTracker
from overlay.minute import estimate_minute
from overlay.model import Match, Status
from overlay.selection import SLOW_INTERVAL, is_focus, next_interval, next_matches
from overlay.service import ScoreService, goal_api_live_fetch

BG = "#111111"
FG = "#ffffff"
COLORS = {Status.LIVE: "#4cff7a", Status.SCHEDULED: "#cccccc", Status.FINISHED: "#888888"}
FONT = "Segoe UI"
NEXT_FG = "#999999"
STALE_FG = "#777777"
FLASH = {"for": "#2ecc40", "against": "#ff4136"}
FLASH_SECONDS = 10
FLASH_MS = 400
TOPMOST_EVERY_MS = 5000
POLL_MS = 500
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MUTEX_NAME = "score-overlay-single-instance"
REPO_URL = "https://codeberg.org/ElvonMF/score-overlay"
LICENSE_NAME = "GPL-3.0-or-later"
FIRST_UPDATE_CHECK = 60          # seconds after start
UPDATE_CHECK_EVERY = 24 * 3600   # seconds


def status_text(info: "updater.UpdateInfo | None") -> str:
    if info is None:
        return "Noch nicht geprüft"
    if info.available:
        suffix = " (letzte Prüfung fehlgeschlagen)" if info.error else ""
        return f"v{info.version} verfügbar{suffix}"
    if info.error:
        return "Prüfung fehlgeschlagen"
    return "Aktuell"


def restart_command(executable: str, start: Path) -> tuple[list[str], dict]:
    """Restarts with pythonw.exe if available, never attached to a console."""
    exe = Path(executable)
    windowless = exe.with_name("pythonw.exe")
    if exe.name.lower() == "python.exe" and windowless.exists():
        exe = windowless
    return [str(exe), str(start)], {"creationflags": subprocess.DETACHED_PROCESS}


def about_lines(version: str, status: str) -> list[str]:
    return [
        "Score-Overlay",
        f"Version {version}",
        f"Lizenz: {LICENSE_NAME}",
        "Copyright (C) 2026 ElvonMF",
        "Ohne jede Gewährleistung – siehe LICENSE",
        REPO_URL,
        "Daten: OpenLigaDB, ESPN, TheSportsDB, optional goal-api.com",
        f"Update: {status}",
    ]


def _virtual_desktop() -> tuple[int, int, int, int]:
    """Bounding box of all monitors (Windows virtual screen)."""
    metric = ctypes.windll.user32.GetSystemMetrics
    return metric(76), metric(77), metric(78), metric(79)


def format_next(m: Match) -> str:
    local = m.kickoff.astimezone()
    return f"{m.home} – {m.away} · {WEEKDAYS[local.weekday()]} {local:%d.%m. %H:%M}"


def _key(m: Match) -> tuple:
    return (m.home, m.away, m.kickoff)


def format_score(m: Match, stale: bool) -> str:
    if m.home_goals is None or m.away_goals is None:
        score = "-:-"
    else:
        score = f"{m.home_goals}:{m.away_goals}"
    return score + "?" if stale else score


def format_suffix(m: Match, now: datetime) -> str:
    if m.status is Status.LIVE:
        return m.minute or estimate_minute(m.kickoff, now)
    if m.status is Status.FINISHED:
        return "Ende"
    return m.kickoff.astimezone().strftime("%H:%M")


class Overlay:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.app_dir = config_path.parent
        self.restart_requested = False
        self.installing = False
        self.update_info: updater.UpdateInfo | None = None
        self.update_events: queue.Queue = queue.Queue()
        self.check_now = threading.Event()
        self.about_window: tk.Toplevel | None = None
        self.about_status: tk.Label | None = None
        self.cfg = config.load(config_path)
        if not config.on_screen(self.cfg, _virtual_desktop()):
            self.cfg = dict(config.DEFAULTS)  # monitor gone or config broken
        key = self.cfg.get("goal_api_key")
        self.service = ScoreService(live_fetch=goal_api_live_fetch(key) if key else None)
        self.service.leagues = config.leagues(self.cfg)
        self.goals = GoalTracker()
        self.results: queue.Queue = queue.Queue()
        self.wake = threading.Event()
        self.row_labels: dict[tuple, tuple[list[tk.Label], str]] = {}
        self.flashing: dict[tuple, tuple[str, float]] = {}
        self.flash_on = False

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg=BG)

        self.clock = tk.Label(self.root, font=(FONT, 20, "bold"), fg=FG, bg=BG)
        self.clock.pack(anchor="e", padx=10, pady=(4, 4))
        self.upcoming = tk.Frame(self.root, bg=BG)
        self.upcoming.pack(anchor="e", padx=10)
        self.table = tk.Frame(self.root, bg=BG)
        self.table.pack(anchor="e", padx=10, pady=(0, 6))

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Aktualisieren", command=self.wake.set)
        self.switches: dict[str, tk.BooleanVar] = {}
        self.menu.add_separator()
        for key, label in (("preview", "Vorschau"), ("all_bl", "Alle Bundesliga-Spiele"),
                           ("all_ucl", "Alle Champions-League-Spiele"), ("sound", "Ton bei Tor")):
            var = tk.BooleanVar(value=bool(self.cfg.get(key)))
            self.switches[key] = var
            self.menu.add_checkbutton(label=label, variable=var,
                                      command=lambda k=key: self._toggle(k))
        self.menu.add_separator()
        self.menu.add_command(label="Über Score-Overlay…", command=self._show_about)
        self.update_entry = False  # whether the menu currently has an update entry
        self.menu.add_command(label="Beenden", command=self.root.destroy)

        self.root.bind_all("<ButtonPress-1>", self._drag_start)
        self.root.bind_all("<B1-Motion>", self._drag_move)
        self.root.bind_all("<ButtonRelease-1>", self._drag_end)
        self.root.bind_all("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        self._tick()
        self._place()
        self._keep_on_top()
        self._poll_results()
        self._flash_tick()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._update_worker, daemon=True).start()

    # --- background fetching -------------------------------------------
    def _worker(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            try:
                matches = self.service.refresh(now)
                upcoming = next_matches(self.service.all_matches(), matches, now)
                goals = self.goals.update(matches)
                stale = self.service.stale_matches()
                interval = next_interval(matches, now)
            except Exception:
                matches, interval = None, SLOW_INTERVAL
            if matches is not None:
                self.results.put((matches, upcoming, goals, stale))
            self.wake.wait(interval)
            self.wake.clear()

    def _poll_results(self) -> None:
        try:
            while True:
                self._render(*self.results.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                self._handle_update_event(*self.update_events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_results)

    # --- drawing ---------------------------------------------------------
    def _tick(self) -> None:
        self.clock.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000 - datetime.now().microsecond // 1000, self._tick)

    def _render(self, matches: list[Match], upcoming: list[tuple[str, Match]],
                goals: dict[Match, str], stale: set[Match]) -> None:
        now = datetime.now(timezone.utc)
        for w in self.upcoming.winfo_children():
            w.destroy()
        for _team, m in (upcoming if self.cfg.get("preview") else []):
            tk.Label(self.upcoming, text=format_next(m), font=(FONT, 9), fg=NEXT_FG, bg=BG,
                     anchor="e").pack(anchor="e")

        for w in self.table.winfo_children():
            w.destroy()
        self.row_labels = {}
        for row, m in enumerate(matches):
            weight = "bold" if is_focus(m) else "normal"
            is_stale = m in stale
            color = STALE_FG if is_stale else COLORS[m.status]
            cells = [m.competition, m.home, format_score(m, is_stale), m.away, format_suffix(m, now)]
            anchors = ["w", "e", "center", "w", "e"]
            labels = []
            for col, (text, anchor) in enumerate(zip(cells, anchors)):
                label = tk.Label(self.table, text=text, font=(FONT, 10, weight), fg=color, bg=BG,
                                 anchor=anchor)
                label.grid(row=row, column=col, sticky="ew", padx=3)
                labels.append(label)
            self.row_labels[_key(m)] = (labels, color)

        until = time.monotonic() + FLASH_SECONDS
        for m, kind in goals.items():
            self.flashing[_key(m)] = (FLASH[kind], until)
        if goals and self.cfg.get("sound"):
            play_goal_sound(self.cfg.get("sound_file"))
        self._layout()
        self._place()

    def _layout(self) -> None:
        """Hide empty sections; an empty Tk frame keeps its last size otherwise."""
        for frame, pady in ((self.upcoming, 0), (self.table, (0, 6))):
            frame.pack_forget()
            if frame.winfo_children():
                frame.pack(anchor="e", padx=10, pady=pady)

    def _flash_tick(self) -> None:
        self.flash_on = not self.flash_on
        now = time.monotonic()
        for key, (flash_color, until) in list(self.flashing.items()):
            active = now < until
            if not active:
                del self.flashing[key]
            labels, fg = self.row_labels.get(key, ([], FG))
            for label in labels:
                if active and self.flash_on:
                    label.config(bg=flash_color, fg="#000000")
                else:
                    label.config(bg=BG, fg=fg)
        self.root.after(FLASH_MS, self._flash_tick)

    def _place(self) -> None:
        """Keep the right edge fixed so the window grows to the left/down."""
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        right = self.cfg.get("right")
        if right is None:
            right = self.root.winfo_screenwidth() - 10
        self.root.geometry(f"+{right - width}+{self.cfg['y']}")

    def _keep_on_top(self) -> None:
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(TOPMOST_EVERY_MS, self._keep_on_top)

    # --- updates ---------------------------------------------------------
    def _update_worker(self) -> None:
        self.check_now.wait(FIRST_UPDATE_CHECK)
        while True:
            self.check_now.clear()
            self.update_events.put(("checked", updater.check(__version__)))
            self.check_now.wait(UPDATE_CHECK_EVERY)

    def _handle_update_event(self, kind: str, payload) -> None:
        if kind == "checked":
            self.update_info = updater.merge_info(self.update_info, payload)
            self._refresh_update_entry()
        elif kind == "installed":
            self.restart_requested = True
            self.root.destroy()
            return
        elif kind == "failed":
            self.installing = False
            self._refresh_update_entry()
            messagebox.showerror("Update fehlgeschlagen", str(payload), parent=self.root)
        if self.about_status is not None and self.about_status.winfo_exists():
            self.about_status.config(text=f"Update: {status_text(self.update_info)}")

    def _refresh_update_entry(self) -> None:
        end = self.menu.index("end")  # "Beenden"
        if self.update_entry:
            self.menu.delete(end - 1)
            self.update_entry = False
            end -= 1
        info = self.update_info
        if not (info and info.available):
            return
        if self.installing:
            self.menu.insert_command(end, label=f"Update auf v{info.version} wird installiert…", state="disabled")
        elif updater.is_git_checkout(self.app_dir):
            self.menu.insert_command(end, label=f"v{info.version} verfügbar – per git pull aktualisieren",
                                     state="disabled")
        else:
            self.menu.insert_command(end, label=f"Update auf v{info.version} installieren",
                                     command=self._install_update)
        self.update_entry = True

    def _install_update(self) -> None:
        if self.installing:
            return
        version = self.update_info.version
        question = f"Version {version} herunterladen und installieren?\nDas Overlay startet danach neu."
        if not messagebox.askyesno("Update", question, parent=self.root):
            return
        self.installing = True
        self._refresh_update_entry()

        def work():
            try:
                updater.download_and_install(version, self.app_dir)
                self.update_events.put(("installed", version))
            except Exception as exc:
                self.update_events.put(("failed", exc))

        threading.Thread(target=work, daemon=True).start()

    def _show_about(self) -> None:
        if self.about_window is not None and self.about_window.winfo_exists():
            self.about_window.lift()
            return
        win = tk.Toplevel(self.root, bg=BG, padx=16, pady=12)
        win.title("Über Score-Overlay")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        lines = about_lines(__version__, status_text(self.update_info))
        for line in lines[:-1]:
            label = tk.Label(win, text=line, font=(FONT, 10, "bold" if line == lines[0] else "normal"),
                             fg=FG, bg=BG, anchor="w")
            if line == REPO_URL:
                label.config(fg="#6cb4ff", cursor="hand2")
                label.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))
            label.pack(anchor="w")
        self.about_status = tk.Label(win, text=lines[-1], font=(FONT, 10), fg=FG, bg=BG, anchor="w")
        self.about_status.pack(anchor="w", pady=(6, 10))
        buttons = tk.Frame(win, bg=BG)
        buttons.pack(anchor="e")
        tk.Button(buttons, text="Nach Updates suchen", command=self._check_from_about).pack(side="left", padx=4)
        tk.Button(buttons, text="Schließen", command=win.destroy).pack(side="left")
        self.about_window = win

    def _check_from_about(self) -> None:
        self.about_status.config(text="Update: Wird geprüft…")
        self.check_now.set()

    # --- dragging --------------------------------------------------------
    def _on_overlay(self, event) -> bool:
        """Mouse bindings are global; only the overlay window itself is draggable."""
        return event.widget.winfo_toplevel() is self.root

    def _drag_start(self, event) -> None:
        if not self._on_overlay(event):
            self._offset = None
            return
        self._offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        if getattr(self, "_offset", None) is None:
            return
        x = event.x_root - self._offset[0]
        y = event.y_root - self._offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, event) -> None:
        if getattr(self, "_offset", None) is None:
            return
        self.cfg["right"] = self.root.winfo_x() + self.root.winfo_width()
        self.cfg["y"] = self.root.winfo_y()
        config.save(self.config_path, config.ui_settings(self.cfg))

    def _toggle(self, key: str) -> None:
        self.cfg[key] = self.switches[key].get()
        config.save(self.config_path, config.ui_settings(self.cfg))
        self.service.leagues = config.leagues(self.cfg)
        self.wake.set()  # re-select and redraw right away


def run(config_path: Path) -> None:
    lock = single_instance.acquire(MUTEX_NAME)
    if lock is None:
        return  # overlay already running
    try:
        overlay = Overlay(config_path)
        overlay.root.mainloop()
    finally:
        single_instance.release(lock)
    if overlay.restart_requested:  # after an update; the lock is free again
        args, kwargs = restart_command(sys.executable, config_path.parent / "start.pyw")
        subprocess.Popen(args, **kwargs)
