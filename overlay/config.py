"""Persists the window position in a small JSON file."""
import json
from pathlib import Path

DEFAULTS = {"right": None, "y": 10}


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
