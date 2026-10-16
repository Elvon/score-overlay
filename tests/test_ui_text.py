from datetime import datetime, timezone

from overlay.model import Match, Status
from overlay.ui import format_next


def test_format_next_uses_local_german_weekday_and_date():
    kickoff = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    m = Match("UCL", "VfB Stuttgart", "Atlético Madrid", None, None, Status.SCHEDULED, kickoff)
    local = kickoff.astimezone()
    weekday = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][local.weekday()]
    assert format_next(m) == f"VfB Stuttgart – Atlético Madrid · {weekday} {local:%d.%m. %H:%M}"


def test_suffix_estimates_minute_when_source_has_none():
    from datetime import timedelta
    from overlay.ui import format_suffix
    kickoff = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)
    m = Match("BL", "A", "B", 1, 0, Status.LIVE, kickoff)
    assert format_suffix(m, kickoff + timedelta(minutes=20)) == "~21'"


def test_suffix_keeps_reported_minute():
    from overlay.ui import format_suffix
    kickoff = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)
    m = Match("UCL", "A", "B", 1, 0, Status.LIVE, kickoff, "67'")
    assert format_suffix(m, kickoff) == "67'"


def test_score_marks_stale():
    from overlay.ui import format_score
    m = Match("BL", "A", "B", 2, 1, Status.LIVE, datetime(2026, 10, 17, tzinfo=timezone.utc))
    assert format_score(m, stale=False) == "2:1"
    assert format_score(m, stale=True) == "2:1?"
