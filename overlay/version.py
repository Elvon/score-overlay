# SPDX-License-Identifier: GPL-3.0-or-later
"""Version strings like "1.5.0" or "v1.5.0"."""
import re

_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int]:
    match = _PATTERN.match(text)
    if not match:
        raise ValueError(f"not a version: {text!r}")
    return tuple(int(part) for part in match.groups())


def is_newer(candidate: str, current: str) -> bool:
    return parse_version(candidate) > parse_version(current)
