import json
from datetime import datetime, timezone
from pathlib import Path

from overlay.model import Status
from overlay.sources.openligadb import parse

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def by_home(matches, home):
    return next(m for m in matches if m.home == home)


def test_finished_uses_highest_result():
    m = by_home(parse(load("oldb_edge.json"), "BL", NOW), "FC Bayern München")
    assert (m.home_goals, m.away_goals, m.status) == (5, 1, Status.FINISHED)


def test_live_score_from_goals():
    m = by_home(parse(load("oldb_edge.json"), "BL", NOW), "SC Freiburg")
    assert (m.home_goals, m.away_goals, m.status) == (1, 1, Status.LIVE)


def test_live_without_data_is_0_0():
    m = by_home(parse(load("oldb_edge.json"), "BL", NOW), "Werder Bremen")
    assert (m.home_goals, m.away_goals, m.status) == (0, 0, Status.LIVE)


def test_scheduled_has_no_score():
    early = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    m = by_home(parse(load("oldb_edge.json"), "BL", early), "Werder Bremen")
    assert (m.home_goals, m.away_goals, m.status) == (None, None, Status.SCHEDULED)


def test_placeholder_kickoff_dropped():
    homes = [m.home for m in parse(load("oldb_edge.json"), "FBL", NOW)]
    assert "Bayer 04 Leverkusen Frauen" not in homes


def test_real_fixture_parses():
    matches = parse(load("oldb_bl1.json"), "BL", NOW)
    assert len(matches) > 200
    assert all(m.kickoff.tzinfo is not None for m in matches)
    assert all(m.competition == "BL" for m in matches)
