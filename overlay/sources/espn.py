"""ESPN scoreboard: international club competitions (UCL, UEL, UECL)."""
from datetime import date, datetime

from overlay.model import Match, Status
from overlay.sources.http import get_json

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={day:%Y%m%d}"

STATES = {"pre": Status.SCHEDULED, "in": Status.LIVE, "post": Status.FINISHED}


def _goals(team: dict) -> int | None:
    try:
        return int(team["score"])
    except (KeyError, TypeError, ValueError):
        return None


def parse(data: dict, competition: str) -> list[Match]:
    matches = []
    for event in data.get("events") or []:
        teams = {t["homeAway"]: t for t in event["competitions"][0]["competitors"]}
        status = STATES.get(event["status"]["type"]["state"], Status.SCHEDULED)
        live = status is Status.LIVE
        scheduled = status is Status.SCHEDULED
        matches.append(Match(
            competition=competition,
            home=teams["home"]["team"]["displayName"],
            away=teams["away"]["team"]["displayName"],
            home_goals=None if scheduled else _goals(teams["home"]),
            away_goals=None if scheduled else _goals(teams["away"]),
            status=status,
            kickoff=datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
            minute=event["status"].get("displayClock") if live else None,
        ))
    return matches


def fetch(league: str, competition: str, day: date) -> list[Match]:
    return parse(get_json(URL.format(league=league, day=day)), competition)
