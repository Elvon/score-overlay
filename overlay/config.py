# SPDX-License-Identifier: GPL-3.0-or-later
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


def save(path: Path, updates: dict) -> None:
    """Merges updates into the file, keeping entries edited by hand (e.g. an API key)."""
    current = load(path)
    path.write_text(json.dumps({**current, **updates}, indent=2), encoding="utf-8")


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


def placed(cfg: dict, desktop: tuple[int, int, int, int]) -> dict:
    """cfg with the default position if the saved one is off screen; all other settings are kept."""
    if on_screen(cfg, desktop):
        return cfg
    return {**cfg, "right": DEFAULTS["right"], "y": DEFAULTS["y"]}


def leagues(cfg: dict) -> frozenset[str]:
    """Competitions whose other matches of the day are shown, per the menu switches."""
    return frozenset(code for code, key in (("BL", "all_bl"), ("UCL", "all_ucl")) if cfg.get(key))


UI_KEYS = ("right", "y", "sound", "preview", "all_bl", "all_ucl", "language")


def ui_settings(cfg: dict) -> dict:
    """The entries the overlay itself changes; everything else is left to the user."""
    return {k: cfg[k] for k in UI_KEYS if k in cfg}
