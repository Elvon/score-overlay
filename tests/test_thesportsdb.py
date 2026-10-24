import json
from datetime import datetime, timezone
from pathlib import Path

from overlay.model import Status
from overlay.sources.thesportsdb import parse

FIX = Path(__file__).parent / "fixtures"
# Shortly after the synthetic 2026-10-13 17:00 UTC kickoffs below.
DURING = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)


def load(name, key):
    return json.loads((FIX / name).read_text(encoding="utf-8"))[key]


def test_tsdb_finished():
    m = next(m for m in parse(load("tsdb_last.json", "results")) if m.away == "Ansbach 09")
    assert m.home == "1860 Munich"
    assert (m.home_goals, m.away_goals, m.status) == (4, 0, Status.FINISHED)
    assert m.competition == "RLB"
    assert m.kickoff == datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_tsdb_next_scheduled():
    m = parse(load("tsdb_next.json", "events"))[0]
    assert (m.home_goals, m.away_goals, m.status) == (None, None, Status.SCHEDULED)


def test_tsdb_empty():
    assert parse([]) == []


def test_tsdb_live_with_null_scores():
    ev = {"strTimestamp": "2026-10-13T17:00:00", "strHomeTeam": "1860 Munich",
          "strAwayTeam": "Bayreuth", "intHomeScore": None, "intAwayScore": "",
          "strStatus": "2H", "strLeague": "German Regionalliga Bayern"}
    m = parse([ev], now=DURING)[0]
    assert m.status is Status.LIVE
    assert (m.home_goals, m.away_goals) == (None, None)


def test_tsdb_halftime_and_cup():
    ev = {"strTimestamp": "2026-10-13T17:00:00", "strHomeTeam": "1860 Munich",
          "strAwayTeam": "Bayreuth", "intHomeScore": "1", "intAwayScore": "0",
          "strStatus": "HT", "strLeague": "DFB-Pokal"}
    m = parse([ev], now=DURING)[0]
    assert (m.status, m.minute, m.competition, m.home_goals) == (Status.LIVE, "HZ", "DFB", 1)


def _ev(status, ts="2026-10-13T17:00:00"):
    return {"strTimestamp": ts, "strHomeTeam": "1860 Munich", "strAwayTeam": "Bayreuth",
            "intHomeScore": "2", "intAwayScore": "1", "strStatus": status,
            "strLeague": "German Regionalliga Bayern"}


def test_tsdb_long_form_finished():
    assert parse([_ev("Match Finished")])[0].status is Status.FINISHED


def test_tsdb_postponed_dropped():
    for s in ["PST", "Postponed", "CANC", "Cancelled", "ABD", "AWD"]:
        assert parse([_ev(s)]) == []


def test_tsdb_live_status_long_after_kickoff_is_finished():
    m = parse([_ev("2H", ts="2026-10-01T17:00:00")], now=datetime(2026, 10, 11, tzinfo=timezone.utc))[0]
    assert m.status is Status.FINISHED


def test_fetch_uses_current_free_key(monkeypatch):
    from overlay.sources import thesportsdb
    urls = []
    monkeypatch.setattr(thesportsdb, "get_json", lambda url: urls.append(url) or {})
    thesportsdb.fetch()
    assert urls and all("/api/v1/json/123/" in u for u in urls)
