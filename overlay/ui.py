"""Borderless, always-on-top overlay window with clock and scores."""
import ctypes
import queue
import threading
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path

from overlay import config
from overlay.model import Match, Status
from overlay.selection import SLOW_INTERVAL, is_focus, next_interval
from overlay.service import ScoreService

BG = "#111111"
FG = "#ffffff"
COLORS = {Status.LIVE: "#4cff7a", Status.SCHEDULED: "#cccccc", Status.FINISHED: "#888888"}
FONT = "Segoe UI"
TOPMOST_EVERY_MS = 5000
POLL_MS = 500


def _virtual_desktop() -> tuple[int, int, int, int]:
    """Bounding box of all monitors (Windows virtual screen)."""
    metric = ctypes.windll.user32.GetSystemMetrics
    return metric(76), metric(77), metric(78), metric(79)


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
        self.results: queue.Queue[list[Match]] = queue.Queue()
        self.wake = threading.Event()

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg=BG)

        self.clock = tk.Label(self.root, font=(FONT, 20, "bold"), fg=FG, bg=BG)
        self.clock.pack(anchor="e", padx=10, pady=(4, 0))
        self.table = tk.Frame(self.root, bg=BG)
        self.table.pack(anchor="e", padx=10, pady=(0, 6))

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Aktualisieren", command=self.wake.set)
        self.menu.add_command(label="Beenden", command=self.root.destroy)

        self.root.bind_all("<ButtonPress-1>", self._drag_start)
        self.root.bind_all("<B1-Motion>", self._drag_move)
        self.root.bind_all("<ButtonRelease-1>", self._drag_end)
        self.root.bind_all("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))

        self._tick()
        self._place()
        self._keep_on_top()
        self._poll_results()
        threading.Thread(target=self._worker, daemon=True).start()

    # --- background fetching -------------------------------------------
    def _worker(self) -> None:
        while True:
            now = datetime.now(timezone.utc)
            try:
                matches = self.service.refresh(now)
                interval = next_interval(matches, now)
            except Exception:
                matches, interval = None, SLOW_INTERVAL
            if matches is not None:
                self.results.put(matches)
            self.wake.wait(interval)
            self.wake.clear()

    def _poll_results(self) -> None:
        try:
            while True:
                self._render(self.results.get_nowait())
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._poll_results)

    # --- drawing ---------------------------------------------------------
    def _tick(self) -> None:
        self.clock.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000 - datetime.now().microsecond // 1000, self._tick)

    def _render(self, matches: list[Match]) -> None:
        for w in self.table.winfo_children():
            w.destroy()
        for row, m in enumerate(matches):
            weight = "bold" if is_focus(m) else "normal"
            color = COLORS[m.status]
            cells = [m.competition, m.home, _score(m), m.away, _suffix(m)]
            anchors = ["w", "e", "center", "w", "e"]
            for col, (text, anchor) in enumerate(zip(cells, anchors)):
                tk.Label(self.table, text=text, font=(FONT, 10, weight), fg=color, bg=BG,
                         anchor=anchor).grid(row=row, column=col, sticky="ew", padx=3)
        self._place()

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
        config.save(self.config_path, {"right": self.cfg["right"], "y": self.cfg["y"]})


def run(config_path: Path) -> None:
    Overlay(config_path).root.mainloop()
