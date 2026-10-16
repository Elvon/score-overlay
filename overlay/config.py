"""Persists the window position in a small JSON file."""
import json
from pathlib import Path

DEFAULTS = {"right": None, "y": 10, "sound": True,
            "preview": True, "all_bl": True, "all_ucl": False,
            "sound_file": r"C:\Windows\Media\tada.wav"}


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    if not isinstance(data, dict):
        return dict(DEFAULTS)
    return {**DEFAULTS, **data}


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


MIN_VISIBLE = 50


def on_screen(cfg: dict, desktop: tuple[int, int, int, int]) -> bool:
    """True if the saved position lies on the virtual desktop (x, y, width, height)."""
    right, y = cfg.get("right"), cfg.get("y")
    if right is None:
        return isinstance(y, int)
    if not isinstance(right, int) or not isinstance(y, int):
        return False
    dx, dy, dw, dh = desktop
    return dx + MIN_VISIBLE <= right <= dx + dw and dy <= y <= dy + dh - MIN_VISIBLE


def leagues(cfg: dict) -> frozenset[str]:
    """Competitions whose other matches of the day are shown, per the menu switches."""
    return frozenset(code for code, key in (("BL", "all_bl"), ("UCL", "all_ucl")) if cfg.get(key))
