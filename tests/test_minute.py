# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timedelta, timezone

import pytest

from overlay.minute import estimate_minute

KICKOFF = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("elapsed, expected", [
    (0, "~1'"),
    (0.5, "~1'"),
    (44.5, "~45'"),
    (45, "~45+'"),
    (47.9, "~45+'"),
    (48, "HZ"),
    (62.9, "HZ"),
    (63, "~46'"),
    (89, "~72'"),
    (107.9, "~90'"),
    (108, "~90+'"),
    (150, "~90+'"),
])
def test_estimate_minute(elapsed, expected):
    assert estimate_minute(KICKOFF, KICKOFF + timedelta(minutes=elapsed)) == expected


def test_before_kickoff_is_first_minute():
    assert estimate_minute(KICKOFF, KICKOFF - timedelta(minutes=1)) == "~1'"
