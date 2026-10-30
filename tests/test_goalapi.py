# SPDX-License-Identifier: GPL-3.0-or-later
import json
from datetime import datetime, timezone
from pathlib import Path

from overlay.model import Status
from overlay.sources.goalapi import parse

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))["data"]


def by_home(matches, home):
    return next(m for m in matches if m.home == home)


def test_live_match_with_real_minute():
    m = by_home(parse(load("goalapi_bl_20261024.json"), "BL"), "Mainz 05")
    assert (m.away, m.home_goals, m.away_goals) == ("Werder Bremen", 0, 2)
    assert (m.status, m.minute, m.competition) == (Status.LIVE, "28'", "BL")
    assert m.kickoff == datetime(2026, 10, 24, 13, 30, tzinfo=timezone.utc)


def test_not_started_has_no_score():
    m = by_home(parse(load("goalapi_bl_20261024.json"), "BL"), "Borussia Dortmund")
    assert (m.status, m.home_goals, m.away_goals, m.minute) == (Status.SCHEDULED, None, None, None)


def test_women_names_and_finished():
    m = by_home(parse(load("goalapi_fbl_20261024.json"), "FBL"), "Stuttgart Frauen")
    assert (m.away, m.home_goals, m.away_goals, m.status) == ("Eintracht Frankfurt Frauen", 0, 3, Status.FINISHED)


def _fixture(period, minute, home="Munich 1860"):
    return {"kickoffUtc": "2026-10-24T12:00:00.000Z", "homeTeam": {"name": home}, "homeTeamName": home,
            "awayTeam": {"name": "Bayreuth"}, "awayTeamName": "Bayreuth",
            "homeTeamScore": 1, "awayTeamScore": 0, "matchPeriod": period, "matchMinute": minute}


def test_half_time_and_stoppage():
    assert parse([_fixture("HALF_TIME", "Half Time")], "RLB")[0].minute == "HZ"
    assert parse([_fixture("SECOND_HALF", "90+3")], "RLB")[0].minute == "90+3'"
    assert parse([_fixture("FIRST_HALF", "45+")], "RLB")[0].minute == "45+'"


def test_unknown_period_like_postponed_dropped():
    assert parse([_fixture("POSTPONED", "Postponed")], "RLB") == []


def test_falls_back_to_flat_team_name():
    f = _fixture("FIRST_HALF", "10")
    del f["homeTeam"]
    assert parse([f], "RLB")[0].home == "Munich 1860"


def test_competition_of_league_names():
    from overlay.sources.goalapi import competition_of
    assert competition_of("DFB Pokal Women - 1/8-finals") == "DFBF"
    assert competition_of("DFB Pokal - 2nd round") == "DFB"
    assert competition_of("Frauen Bundesliga") == "FBL"
    assert competition_of("Bundesliga") == "BL"
    assert competition_of("Regionalliga - Bayern") == "RLB"
    assert competition_of("2. Bundesliga Women") is None
    assert competition_of("Oberliga") is None


def test_parse_team_schedule_includes_womens_cup():
    from overlay.sources.goalapi import parse_team
    matches = parse_team(load("goalapi_vfb_women_fixtures.json"))
    cup = next(m for m in matches if m.kickoff == datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc))
    assert (cup.competition, cup.home, cup.away, cup.status) == (
        "DFBF", "Stuttgart Frauen", "SGS Essen Frauen", Status.SCHEDULED)
    assert {m.competition for m in matches} <= {"DFBF", "FBL"}
