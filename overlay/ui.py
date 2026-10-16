"""Borderless, always-on-top overlay window with clock and scores."""
import ctypes
import queue
import threading
import time
import tkinter as tk
import winsound
from datetime import datetime, timezone
from pathlib import Path

from overlay import config, single_instance
from overlay.goals import GoalTracker
from overlay.model import Match, Status
from overlay.selection import SLOW_INTERVAL, is_focus, next_interval, next_matches
from overlay.service import ScoreService

BG = "#111111"
FG = "#ffffff"
COLORS = {Status.LIVE: "#4cff7a", Status.SCHEDULED: "#cccccc", Status.FINISHED: "#888888"}
FONT = "Segoe UI"
NEXT_FG = "#999999"
FLASH = {"for": "#2ecc40", "against": "#ff4136"}
FLASH_SECONDS = 10
FLASH_MS = 400
TOPMOST_EVERY_MS = 5000
POLL_MS = 500
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MUTEX_NAME = "score-overlay-single-instance"


def _virtual_desktop() -> tuple[int, int, int, int]:
    """Bounding box of all monitors (Windows virtual screen)."""
    metric = ctypes.windll.user32.GetSystemMetrics
    return metric(76), metric(77), metric(78), metric(79)


def format_next(m: Match) -> str:
    local = m.kickoff.astimezone()
    return f"{m.home} – {m.away} · {WEEKDAYS[local.weekday()]} {local:%d.%m. %H:%M}"


def _key(m: Match) -> tuple:
    return (m.home, m.away, m.kickoff)


def _score(m: Match) -> str:
    if m.home_goals is None or m.away_goals is None:
        return "-:-"
    return f"{m.home_goals}:{m.away_goals}"


def _suffix(m: Match) -> str:
    if m.status is Status.LIVE:
        return m.minute or "live"
    if m.status is Status.FINISHED:
        return "Ende"
    return m.kickoff.astimezone().strftime("%H:%M")


class Overlay:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.cfg = config.load(config_path)
        if not config.on_screen(self.cfg, _virtual_desktop()):
            self.cfg = dict(config.DEFAULTS)  # monitor gone or config broken
        self.service = ScoreService()
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

    # --- background fetching -------------------------------------------
    def _worker(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            try:
                matches = self.service.refresh(now)
                upcoming = next_matches(self.service.all_matches(), matches, now)
                goals = self.goals.update(matches)
                interval = next_interval(matches, now)
            except Exception:
                matches, interval = None, SLOW_INTERVAL
            if matches is not None:
                self.results.put((matches, upcoming, goals))
            self.wake.wait(interval)
            self.wake.clear()

    def _poll_results(self) -> None:
        try:
            while True:
                self._render(*self.results.get_nowait())
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_results)

    # --- drawing ---------------------------------------------------------
    def _tick(self) -> None:
        self.clock.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000 - datetime.now().microsecond // 1000, self._tick)

    def _render(self, matches: list[Match], upcoming: list[tuple[str, Match]],
                goals: dict[Match, str]) -> None:
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
            color = COLORS[m.status]
            cells = [m.competition, m.home, _score(m), m.away, _suffix(m)]
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
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
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

    # --- dragging --------------------------------------------------------
    def _drag_start(self, event) -> None:
        self._offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_move(self, event) -> None:
        x = event.x_root - self._offset[0]
        y = event.y_root - self._offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _drag_end(self, event) -> None:
        self.cfg["right"] = self.root.winfo_x() + self.root.winfo_width()
        self.cfg["y"] = self.root.winfo_y()
        config.save(self.config_path, self.cfg)

    def _toggle(self, key: str) -> None:
        self.cfg[key] = self.switches[key].get()
        config.save(self.config_path, self.cfg)
        self.service.leagues = config.leagues(self.cfg)
        self.wake.set()  # re-select and redraw right away


def run(config_path: Path) -> None:
    lock = single_instance.acquire(MUTEX_NAME)
    if lock is None:
        return  # overlay already running
    try:
        Overlay(config_path).root.mainloop()
    finally:
        single_instance.release(lock)
