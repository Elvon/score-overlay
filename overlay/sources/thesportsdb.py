"""TheSportsDB (free key "3"): TSV 1860 München, Regionalliga Bayern."""
from datetime import datetime, timezone

from overlay.model import Match, Status
from overlay.sources.http import get_json

BASE = "https://www.thesportsdb.com/api/v1/json/3"
TEAM_1860 = 134242

FINISHED = {"FT", "AET", "PEN", "AP"}
NOT_STARTED = {"NS", "TBD", "", None}


def _goals(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse(events: list[dict]) -> list[Match]:
    matches = []
    for ev in events:
        raw = ev.get("strStatus")
        if raw in FINISHED:
            status, minute = Status.FINISHED, None
        elif raw in NOT_STARTED:
            status, minute = Status.SCHEDULED, None
        else:
            status, minute = Status.LIVE, ("HZ" if raw == "HT" else None)
        scheduled = status is Status.SCHEDULED
        matches.append(Match(
            competition="RLB" if "Regionalliga" in (ev.get("strLeague") or "") else "DFB",
            home=ev["strHomeTeam"],
            away=ev["strAwayTeam"],
            home_goals=None if scheduled else _goals(ev.get("intHomeScore")),
            away_goals=None if scheduled else _goals(ev.get("intAwayScore")),
            status=status,
            kickoff=datetime.fromisoformat(ev["strTimestamp"]).replace(tzinfo=timezone.utc),
            minute=minute,
        ))
    return matches


def fetch(team_id: int = TEAM_1860) -> list[Match]:
    last = get_json(f"{BASE}/eventslast.php?id={team_id}").get("results") or []
    nxt = get_json(f"{BASE}/eventsnext.php?id={team_id}").get("events") or []
    return parse(last + nxt)
