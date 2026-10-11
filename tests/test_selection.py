from datetime import datetime, timedelta

from overlay.model import Match, Status
from overlay.selection import is_focus, next_interval, select

# Local noon, timezone-aware in the system's local zone.
NOW = datetime(2026, 10, 11, 12, 0).astimezone()
H = timedelta(hours=1)


def mk(comp, home, away, status, kickoff):
    goals = None if status is Status.SCHEDULED else 0
    return Match(comp, home, away, goals, goals, status, kickoff)


def test_is_focus():
    for name in ["VfB Stuttgart", "VfB Stuttgart Frauen", "TSV 1860 München", "1860 Munich"]:
        assert is_focus(mk("BL", name, "X", Status.SCHEDULED, NOW))
    for name in ["VfB Stuttgart II", "FC Bayern München"]:
        assert not is_focus(mk("BL", name, "X", Status.SCHEDULED, NOW))
    assert is_focus(mk("BL", "X", "VfB Stuttgart", Status.SCHEDULED, NOW))


def test_bundesliga_today_all_shown():
    today = [
        mk("BL", "A", "B", Status.FINISHED, NOW - 3 * H),
        mk("BL", "C", "D", Status.LIVE, NOW - H),
        mk("BL", "E", "F", Status.SCHEDULED, NOW + 6 * H),
    ]
    tomorrow = mk("BL", "G", "H", Status.SCHEDULED, NOW + 24 * H)
    shown = select(today + [tomorrow], NOW)
    assert set(shown) == set(today)


def test_focus_window():
    soon = mk("UCL", "VfB Stuttgart", "Atletico Madrid", Status.SCHEDULED, NOW + 2 * H)
    later = mk("UCL", "VfB Stuttgart", "Inter", Status.SCHEDULED, NOW + 4 * H)
    recent = mk("RLB", "1860 Munich", "Bayreuth", Status.FINISHED, NOW - 4 * H)
    old = mk("RLB", "1860 Munich", "Ansbach 09", Status.FINISHED, NOW - 6 * H)
    assert select([soon, later, recent, old], NOW) == [recent, soon]


def test_live_bl_from_yesterday_shown():
    m = mk("BL", "A", "B", Status.LIVE, NOW - 24 * H)
    assert select([m], NOW) == [m]


def test_non_focus_non_bl_hidden():
    m = mk("DFB", "Hansa Rostock", "SC Verl", Status.LIVE, NOW - H)
    assert select([m], NOW) == []


def test_sort_focus_first():
    bl = mk("BL", "A", "B", Status.SCHEDULED, NOW + 3 * H)
    vfb = mk("BL", "VfB Stuttgart", "C", Status.SCHEDULED, NOW + 2.5 * H + 3 * H / 3)
    assert select([bl, vfb], NOW) == [vfb, bl]


def test_dedupe():
    m = mk("BL", "VfB Stuttgart", "A", Status.LIVE, NOW - H)
    assert select([m, m], NOW) == [m]


def test_next_interval():
    live = mk("BL", "A", "B", Status.LIVE, NOW - H)
    starting = mk("UCL", "VfB Stuttgart", "A", Status.SCHEDULED, NOW + timedelta(minutes=10))
    waiting = mk("BL", "A", "B", Status.SCHEDULED, NOW + 2 * H)
    assert next_interval([live], NOW) == 30
    assert next_interval([starting], NOW) == 30
    assert next_interval([waiting], NOW) == 600
    assert next_interval([], NOW) == 600


def test_next_interval_fast_when_scheduled_focus_kickoff_passed():
    late = mk("UCL", "VfB Stuttgart", "A", Status.SCHEDULED, NOW - timedelta(minutes=1))
    assert next_interval([late], NOW) == 30
