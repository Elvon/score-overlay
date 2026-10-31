# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from overlay import i18n


@pytest.fixture(autouse=True)
def german_ui():
    """Most tests check German texts; do not depend on the Windows language of the test machine."""
    i18n.set_language("de")
    yield
    i18n.set_language("de")
