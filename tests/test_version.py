# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

import overlay
from overlay.version import is_newer, parse_version


def test_parse_version():
    assert parse_version("v1.5.0") == (1, 5, 0)
    assert parse_version("1.10.0") == (1, 10, 0)


@pytest.mark.parametrize("text", ["1.5", "v1.6.0-beta", "", "x1.5.0"])
def test_parse_version_rejects(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_is_newer():
    assert is_newer("1.10.0", "1.9.0")
    assert not is_newer("1.5.0", "1.5.0")
    assert not is_newer("1.4.9", "1.5.0")


def test_installed_version():
    assert overlay.__version__ == "1.6.0"
    parse_version(overlay.__version__)
