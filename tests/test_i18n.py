# SPDX-License-Identifier: GPL-3.0-or-later
import string
from datetime import datetime

import pytest

from overlay import i18n


def _fields(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_languages_have_same_keys_and_placeholders():
    de, en = i18n.STRINGS["de"], i18n.STRINGS["en"]
    assert de.keys() == en.keys()
    for key in de:
        assert _fields(de[key]) == _fields(en[key]), key


def test_t_uses_current_language():
    i18n.set_language("en")
    assert i18n.t("menu_quit") == "Quit"
    i18n.set_language("de")
    assert i18n.t("menu_quit") == "Beenden"


def test_t_formats_values():
    i18n.set_language("en")
    assert i18n.t("update_install", version="1.6.0") == "Install update to v1.6.0"


def test_t_does_not_reformat_values():
    i18n.set_language("en")
    assert i18n.t("err_download", error="bad {x}") == "Download failed: bad {x}"


def test_unknown_language_falls_back_to_english():
    i18n.set_language("fr")
    assert i18n.language() == "en"


@pytest.mark.parametrize("langid, expected", [
    (0x0407, "de"), (0x0807, "de"), (0x0C07, "de"), (0x0409, "en"), (0x040C, "en")])
def test_system_language(langid, expected):
    assert i18n.system_language(lambda: langid) == expected


def test_system_language_error_is_english():
    def boom():
        raise OSError
    assert i18n.system_language(boom) == "en"


@pytest.mark.parametrize("configured, expected", [
    ("de", "de"), ("en", "en"), ("fr", "de"), (42, "de"), (None, "de")])
def test_resolve(configured, expected):
    assert i18n.resolve(configured, lambda: 0x0407) == expected


def test_short_date():
    dt = datetime(2026, 10, 31, 18, 0)  # Saturday
    i18n.set_language("de")
    assert i18n.short_date(dt) == "Sa 31.10."
    i18n.set_language("en")
    assert i18n.short_date(dt) == "Sat 31 Oct"
