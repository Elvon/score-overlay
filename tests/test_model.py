from datetime import date, datetime, timezone

from overlay.model import Match, Status, season_for


def test_season_for():
    assert season_for(date(2026, 10, 11)) == 2026
    assert season_for(date(2027, 3, 1)) == 2026
    assert season_for(date(2026, 7, 1)) == 2026
    assert season_for(date(2026, 6, 30)) == 2025


def test_match_is_hashable():
    m = Match("BL", "A", "B", 1, 0, Status.LIVE, datetime(2026, 10, 11, 13, 30, tzinfo=timezone.utc))
    assert hash(m) == hash(Match("BL", "A", "B", 1, 0, Status.LIVE, m.kickoff))
