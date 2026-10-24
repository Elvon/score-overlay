# SPDX-License-Identifier: GPL-3.0-or-later
"""Start the score overlay without a console window (double-click or pythonw)."""
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

logging.basicConfig(filename=HERE / "overlay.log", level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from overlay.ui import run  # noqa: E402

run(HERE / "config.json")
