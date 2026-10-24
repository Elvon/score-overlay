"""goal-api.com (needs a free API key): reliable live scores for today's matches."""
from datetime import date, datetime

from overlay.model import Match, Status
from overlay.sources.http import get_json

BASE = "https://api.goal-api.com/v1"
# goal-api league ids per overlay competition code.
LEAGUES = {
    "BL": "cmr77dvgm0002rx06rt2uqxii",
    "DFB": "cmr77dvgm0003rx06nnbqia6t",
    "FBL": "cmr77dvgm0008rx06s61intpw",
    "RLB": "cmr77dvgm000arx06ghs089wq",  # all Regionalliga divisions
}
LIVE_PERIODS = {"FIRST_HALF", "SECOND_HALF", "EXTRA_TIME", "PENALTIES"}


def _goals(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _name(f: dict, side: str) -> str:
    name = (f.get(f"{side}Team") or {}).get("name") or f[f"{side}TeamName"]
    return name[:-2] + " Frauen" if name.endswith(" W") else name


def parse(fixtures: list[dict], competition: str) -> list[Match]:
    matches = []
    for f in fixtures:
        period = f.get("matchPeriod")
        if period == "NOT_STARTED":
            status, minute = Status.SCHEDULED, None
        elif period == "FINISHED":
            status, minute = Status.FINISHED, None
        elif period == "HALF_TIME":
            status, minute = Status.LIVE, "HZ"
        elif period in LIVE_PERIODS:
            status, minute = Status.LIVE, f"{f.get('matchMinute')}'"
        else:  # postponed, cancelled, unknown
            continue
        scheduled = status is Status.SCHEDULED
        matches.append(Match(
            competition=competition,
            home=_name(f, "home"),
            away=_name(f, "away"),
            home_goals=None if scheduled else _goals(f.get("homeTeamScore")),
            away_goals=None if scheduled else _goals(f.get("awayTeamScore")),
            status=status,
            kickoff=datetime.fromisoformat(f["kickoffUtc"].replace("Z", "+00:00")),
            minute=minute,
        ))
    return matches


def fetch(competition: str, day: date, key: str) -> list[Match]:
    url = f"{BASE}/fixtures/date/{day:%Y-%m-%d}?leagueId={LEAGUES[competition]}&limit=100"
    return parse(get_json(url, headers={"Authorization": f"Bearer {key}"})["data"], competition)
