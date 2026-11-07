# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from dataclasses import replace
from datetime import datetime, timedelta

from overlay.model import Goal, Match, Status
from overlay.service import GOALS_RETRIES, ScoreService

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


def test_women_schedule_only_with_goal_api_key():
    from overlay.service import default_fetchers
    assert "vfb_women_schedule" in default_fetchers("key")
    assert "vfb_women_schedule" not in default_fetchers()


def test_throttled_fetch_at_most_once_per_interval():
    from overlay.service import throttled
    calls = []
    fetch = throttled(lambda now: calls.append(now) or [GA_TODAY], timedelta(hours=1))
    for minutes in (0, 10, 59, 60):
        assert fetch(NOW + timedelta(minutes=minutes)) == [GA_TODAY]
    assert len(calls) == 2


def test_womens_cup_shows_in_preview():
    from overlay.selection import next_matches
    cup = Match("DFBF", "Stuttgart Frauen", "SGS Essen Frauen", None, None, Status.SCHEDULED,
                NOW + timedelta(days=4))
    league = Match("FBL", "1. FSV Mainz 05 Frauen", "VfB Stuttgart Frauen", None, None, Status.SCHEDULED,
                   NOW + timedelta(days=13))
    service = ScoreService({"ffb1": lambda now: [league], "ws": lambda now: [cup]})
    shown = service.refresh(NOW)
    assert ("VfB Frauen", cup) in next_matches(service.all_matches(), shown, NOW)


def test_womens_cup_match_day_uses_own_live_competition():
    cup_today = Match("DFBF", "Stuttgart Frauen", "SGS Essen Frauen", None, None, Status.SCHEDULED,
                      NOW + timedelta(hours=2))
    men_cup_today = Match("DFB", "SC Paderborn 07", "VfB Stuttgart", None, None, Status.SCHEDULED,
                          NOW + timedelta(hours=6))
    calls = []

    def live(comp, now):
        calls.append(comp)
        return {"DFBF": [cup_today], "DFB": [men_cup_today]}[comp]

    service = ScoreService({"ws": lambda now: [cup_today], "dfb": lambda now: [men_cup_today]},
                           live_fetch=live)
    service.refresh(NOW)
    assert sorted(calls) == ["DFB", "DFBF"]
    assert cup_today in service.all_matches()
    assert men_cup_today in service.all_matches()


def test_throttled_fetch_does_not_retry_failures_within_interval():
    from overlay.service import throttled
    calls = []

    def failing(now):
        calls.append(now)
        raise OSError("limit reached")

    fetch = throttled(failing, timedelta(hours=1))
    with pytest.raises(OSError):
        fetch(NOW)
    assert fetch(NOW + timedelta(minutes=30)) == []
    with pytest.raises(OSError):
        fetch(NOW + timedelta(hours=1))
    assert len(calls) == 2


def ga_live(home_goals, away_goals):
    return Match("BL", "Köln", "Schalke 04", home_goals, away_goals, Status.LIVE,
                 NOW - timedelta(minutes=30), "30'", ref="f1")


class GoalsSource:
    def __init__(self, *goals):
        self.goals = goals
        self.calls = []

    def __call__(self, ref):
        self.calls.append(ref)
        if isinstance(self.goals, Exception):
            raise self.goals
        return self.goals


G1 = Goal("12'", "M. Muheim", True)
G2 = Goal("40'", "J. Scally", True)


def goal_service(live, goals):
    return ScoreService({"bl1": lambda now: [OLDB_TODAY]}, live_fetch=live, goals_fetch=goals)


def test_goal_details_fetched_once_per_score():
    live, goals = LiveSource([ga_live(1, 0)]), GoalsSource(G1)
    service = goal_service(live, goals)
    assert service.refresh(NOW)[0].goals == (G1,)
    assert service.refresh(NOW + timedelta(minutes=1))[0].goals == (G1,)
    assert goals.calls == ["f1"]
    live.result, goals.goals = [ga_live(2, 0)], (G1, G2)
    assert service.refresh(NOW + timedelta(minutes=2))[0].goals == (G1, G2)
    assert goals.calls == ["f1", "f1"]


def test_no_goal_details_for_goalless_match():
    goals = GoalsSource()
    goal_service(LiveSource([ga_live(0, 0)]), goals).refresh(NOW)
    assert goals.calls == []


def test_goal_details_failure_keeps_old_goals():
    live, goals = LiveSource([ga_live(1, 0)]), GoalsSource(G1)
    service = goal_service(live, goals)
    service.refresh(NOW)
    live.result, goals.goals = [ga_live(2, 0)], OSError("down")
    assert service.refresh(NOW + timedelta(minutes=1))[0].goals == (G1,)
    goals.goals = (G1, G2)
    assert service.refresh(NOW + timedelta(minutes=2))[0].goals == (G1, G2)
    assert len(goals.calls) == 3


def test_goal_details_retry_limited_when_incomplete():
    live, goals = LiveSource([ga_live(2, 0)]), GoalsSource(G1)
    service = goal_service(live, goals)
    for minute in range(10):
        assert service.refresh(NOW + timedelta(minutes=minute))[0].goals == (G1,)
    assert len(goals.calls) == GOALS_RETRIES


def test_goal_details_without_goals_fetch():
    service = ScoreService({"bl1": lambda now: [OLDB_TODAY]}, live_fetch=LiveSource([ga_live(1, 0)]))
    assert service.refresh(NOW)[0].goals == ()


def test_goal_details_dropped_after_the_matchday():
    live, goals = LiveSource([ga_live(1, 0)]), GoalsSource(G1)
    service = goal_service(live, goals)
    service.refresh(NOW)
    assert service.goal_details
    service.live["BL"] = [replace(ga_live(1, 0), status=Status.FINISHED)]
    service.fetchers = {"bl1": lambda now: [OLDB_NEXT_WEEK]}
    service.refresh(NOW + timedelta(days=1))
    assert service.goal_details == {}
