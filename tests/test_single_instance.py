# SPDX-License-Identifier: GPL-3.0-or-later
from overlay.single_instance import acquire, release

NAME = "score-overlay-test-mutex"


def test_second_acquire_fails_until_released():
    first = acquire(NAME)
    assert first is not None
    try:
        assert acquire(NAME) is None
    finally:
        release(first)
    again = acquire(NAME)
    assert again is not None
    release(again)
