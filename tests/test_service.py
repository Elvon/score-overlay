# SPDX-License-Identifier: GPL-3.0-or-later
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


# --- goal-api as live source -------------------------------------------------
OLDB_TODAY = Match("BL", "1. FC Köln", "FC Schalke 04", 0, 0, Status.LIVE, NOW - timedelta(minutes=30))
OLDB_NEXT_WEEK = Match("BL", "Hamburger SV", "VfB Stuttgart", None, None, Status.SCHEDULED,
                       NOW + timedelta(days=7))
GA_TODAY = Match("BL", "Köln", "Schalke 04", 0, 1, Status.LIVE, NOW - timedelta(minutes=30), "30'")


class LiveSource:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, competition, now):
        self.calls.append((competition, now))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_live_source_replaces_todays_matches_but_keeps_preview():
    live = LiveSource([GA_TODAY])
    service = ScoreService({"bl1": lambda now: [OLDB_TODAY, OLDB_NEXT_WEEK]}, live_fetch=live)
    assert service.refresh(NOW) == [GA_TODAY]
    assert OLDB_NEXT_WEEK in service.all_matches()
    assert OLDB_TODAY not in service.all_matches()


def test_live_source_only_asked_for_competitions_playing_today():
    women = Match("FBL", "VfB Stuttgart Frauen", "SGS Essen Frauen", None, None, Status.SCHEDULED,
                  NOW + timedelta(hours=2))
    live = LiveSource([])
    ScoreService({"x": lambda now: [women, OLDB_NEXT_WEEK]}, live_fetch=live).refresh(NOW)
    assert [c for c, _ in live.calls] == ["FBL"]


def test_live_source_every_minute_while_live():
    live = LiveSource([GA_TODAY])
    service = ScoreService({"bl1": lambda now: [OLDB_TODAY]}, live_fetch=live)
    for seconds in (0, 30, 60):
        service.refresh(NOW + timedelta(seconds=seconds))
    assert len(live.calls) == 2


def test_live_source_every_30_minutes_when_nothing_live():
    later = Match("BL", "A", "B", None, None, Status.SCHEDULED, NOW + timedelta(hours=5))
    live = LiveSource([later])
    service = ScoreService({"bl1": lambda now: [later]}, live_fetch=live)
    for minutes in (0, 10, 29, 30):
        service.refresh(NOW + timedelta(minutes=minutes))
    assert len(live.calls) == 2


def test_live_source_failure_marks_stale_then_falls_back():
    live = LiveSource([GA_TODAY])
    service = ScoreService({"bl1": lambda now: [OLDB_TODAY]}, live_fetch=live)
    service.refresh(NOW)
    live.result = OSError("429 limit reached")
    assert service.refresh(NOW + timedelta(minutes=1)) == [GA_TODAY]
    assert GA_TODAY in service.stale_matches()
    assert service.refresh(NOW + timedelta(minutes=7)) == [OLDB_TODAY]


def test_live_source_stops_after_the_matchday():
    finished = Match("BL", "Köln", "Schalke 04", 1, 1, Status.FINISHED, NOW - timedelta(hours=2))
    live = LiveSource([finished])
    service = ScoreService({"bl1": lambda now: [OLDB_NEXT_WEEK]}, live_fetch=live)
    service.live["BL"] = [finished]  # state left over from the matchday
    service.refresh(NOW + timedelta(days=1))
    service.refresh(NOW + timedelta(days=1, hours=1))
    assert live.calls == []


def test_goal_api_live_fetch_uses_local_date_and_key(monkeypatch):
    from overlay import service as svc
    seen = {}
    monkeypatch.setattr(svc.goalapi, "fetch",
                        lambda comp, day, key: seen.update(comp=comp, day=day, key=key) or [])
    svc.goal_api_live_fetch("k")("FBL", NOW)
    assert seen == {"comp": "FBL", "day": NOW.astimezone().date(), "key": "k"}
