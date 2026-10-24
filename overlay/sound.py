# SPDX-License-Identifier: GPL-3.0-or-later
"""Goal sound: plays a WAV file itself, independent of the Windows sound scheme."""
import winsound
from pathlib import Path

FLAGS = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT


def play_goal_sound(path: str | None, play=winsound.PlaySound, beep=winsound.MessageBeep) -> None:
    if path and Path(path).is_file():
        play(path, FLAGS)
    else:
        beep(winsound.MB_ICONASTERISK)
