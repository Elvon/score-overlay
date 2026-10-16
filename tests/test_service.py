from datetime import datetime, timedelta

from overlay.model import Match, Status
from overlay.service import ScoreService

NOW = datetime(2026, 10, 11, 12, 0).astimezone()
BL = Match("BL", "A", "B", 0, 0, Status.LIVE, NOW - timedelta(hours=1))
VFB = Match("UCL", "VfB Stuttgart", "C", 1, 0, Status.LIVE, NOW - timedelta(hours=1))


def failing(now):
    raise OSError("network down")


def test_failing_source_isolated():
    service = ScoreService({"a": lambda now: [BL], "b": failing})
    assert service.refresh(NOW) == [BL]


def test_failing_source_keeps_cache():
    calls = []

    def flaky(now):
        calls.append(now)
        if len(calls) > 1:
            raise ValueError("bad json")
        return [VFB]

    service = ScoreService({"b": flaky})
    assert service.refresh(NOW) == [VFB]
    assert service.refresh(NOW) == [VFB]


def test_only_hot_sources_refetched_on_fast_cycle():
    calls = {"hot": 0, "cold": 0}
    cold_match = Match("BL", "C", "D", None, None, Status.SCHEDULED, NOW + timedelta(hours=5))

    def hot(now):
        calls["hot"] += 1
        return [VFB]

    def cold(now):
        calls["cold"] += 1
        return [cold_match]

    service = ScoreService({"hot": hot, "cold": cold})
    service.refresh(NOW)
    service.refresh(NOW + timedelta(seconds=30))
    assert calls == {"hot": 2, "cold": 1}
    service.refresh(NOW + timedelta(minutes=11))
    assert calls == {"hot": 3, "cold": 2}


def test_all_matches_includes_unshown_upcoming():
    future = Match("BL", "Hamburger SV", "VfB Stuttgart", None, None, Status.SCHEDULED,
                   NOW + timedelta(days=3))
    service = ScoreService({"a": lambda now: [BL, future]})
    assert service.refresh(NOW) == [BL]
    assert set(service.all_matches()) == {BL, future}


def test_default_fetchers_include_vfb_schedule():
    from overlay.service import default_fetchers
    assert "vfb_ucl_schedule" in default_fetchers()


def test_service_uses_selected_leagues():
    ucl = Match("UCL", "Real Madrid", "FC Liverpool", None, None, Status.SCHEDULED,
                NOW + timedelta(hours=2))
    service = ScoreService({"a": lambda now: [BL, ucl]})
    service.leagues = frozenset({"UCL"})
    assert service.refresh(NOW) == [ucl]


def test_failed_source_marks_its_matches_stale_until_next_success():
    state = {"fail": False}

    def flaky(now):
        if state["fail"]:
            raise OSError("down")
        return [VFB]

    service = ScoreService({"a": flaky, "b": lambda now: [BL]})
    service.refresh(NOW)
    assert service.stale_matches() == set()
    state["fail"] = True
    service.refresh(NOW + timedelta(seconds=30))
    assert service.stale_matches() == {VFB}
    state["fail"] = False
    service.refresh(NOW + timedelta(seconds=60))
    assert service.stale_matches() == set()
