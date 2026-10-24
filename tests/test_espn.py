# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from overlay.model import Status
from overlay.sources.espn import parse

FIX = Path(__file__).parent / "fixtures"


def load():
    return json.loads((FIX / "espn_ucl_20260909.json").read_text(encoding="utf-8"))


def test_espn_finished_vfb():
    m = next(m for m in parse(load(), "UCL") if m.home == "VfB Stuttgart")
    assert m.away == "Viking FK"
    assert (m.home_goals, m.away_goals, m.status) == (3, 1, Status.FINISHED)
    assert m.competition == "UCL"
    assert m.kickoff == datetime(2026, 9, 9, 16, 45, tzinfo=timezone.utc)


def test_espn_live_minute():
    data = load()
    event = copy.deepcopy(data["events"][0])
    event["status"]["type"]["state"] = "in"
    event["status"]["displayClock"] = "67'"
    m = parse({"events": [event]}, "UCL")[0]
    assert m.status is Status.LIVE
    assert m.minute == "67'"


def test_espn_scheduled_has_no_score():
    event = copy.deepcopy(load()["events"][0])
    event["status"]["type"]["state"] = "pre"
    m = parse({"events": [event]}, "UCL")[0]
    assert (m.home_goals, m.away_goals, m.status) == (None, None, Status.SCHEDULED)


def test_schedule_returns_upcoming_vfb_matches():
    from overlay.sources.espn import parse_schedule
    data = json.loads((FIX / "espn_vfb_ucl_schedule.json").read_text(encoding="utf-8"))
    matches = parse_schedule(data, "UCL")
    assert all(m.status is Status.SCHEDULED for m in matches)
    atletico = next(m for m in matches if m.away.startswith("Atl"))
    assert atletico.home == "VfB Stuttgart"
    assert atletico.kickoff == datetime(2026, 10, 20, 19, 0, tzinfo=timezone.utc)
    assert atletico.competition == "UCL"
    # the match that is live in the fixture is left to the scoreboard source
    assert not any(m.home == "Slovan Bratislava" for m in matches)
