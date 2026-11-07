# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date, datetime, timezone

from overlay.model import HALF_TIME, Goal, Match, Status, season_for


def test_season_for():
    assert season_for(date(2026, 10, 11)) == 2026
    assert season_for(date(2027, 3, 1)) == 2026
    assert season_for(date(2026, 7, 1)) == 2026
    assert season_for(date(2026, 6, 30)) == 2025


def test_match_is_hashable():
    m = Match("BL", "A", "B", 1, 0, Status.LIVE, datetime(2026, 10, 11, 13, 30, tzinfo=timezone.utc))
    assert hash(m) == hash(Match("BL", "A", "B", 1, 0, Status.LIVE, m.kickoff))


def test_half_time_marker_is_language_neutral():
    assert HALF_TIME == "HT"


def test_goals_and_ref_do_not_affect_identity():
    k = datetime(2026, 11, 7, 14, 30, tzinfo=timezone.utc)
    a = Match("BL", "A", "B", 1, 0, Status.LIVE, k)
    b = Match("BL", "A", "B", 1, 0, Status.LIVE, k,
              goals=(Goal("12'", "X. Y", True),), ref="abc")
    assert a == b and hash(a) == hash(b)
    assert b.goals[0] == Goal("12'", "X. Y", True, penalty=False, own_goal=False)
