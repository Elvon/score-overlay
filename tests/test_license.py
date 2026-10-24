# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = "# SPDX-License-Identifier: GPL-3.0-or-later"
SKIP = {".git", ".update-backup", "docs", ".superpowers", ".pytest_cache", "__pycache__"}


def python_files():
    for path in [*ROOT.rglob("*.py"), ROOT / "start.pyw"]:
        if not SKIP.intersection(path.relative_to(ROOT).parts):
            yield path


def test_every_python_file_has_spdx_header():
    missing = [str(p.relative_to(ROOT)) for p in python_files()
               if p.read_text(encoding="utf-8").splitlines()[:1] != [HEADER]]
    assert missing == []


def test_license_file_is_gpl3():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text
