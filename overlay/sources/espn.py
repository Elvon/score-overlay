"""ESPN scoreboard: international club competitions (UCL, UEL, UECL)."""
from datetime import date, datetime

from overlay.model import Match, Status
from overlay.sources.http import get_json

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={day:%Y%m%d}"
SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team_id}/schedule?fixture=true"
TEAM_VFB = 134

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


def parse_schedule(data: dict, competition: str) -> list[Match]:
    """Upcoming matches from a team schedule; live/finished ones come from the scoreboard."""
    matches = []
    for event in data.get("events") or []:
        comp = event["competitions"][0]
        if comp["status"]["type"]["state"] != "pre":
            continue
        teams = {t["homeAway"]: t for t in comp["competitors"]}
        matches.append(Match(
            competition=competition,
            home=teams["home"]["team"]["displayName"],
            away=teams["away"]["team"]["displayName"],
            home_goals=None,
            away_goals=None,
            status=Status.SCHEDULED,
            kickoff=datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
        ))
    return matches


def fetch_schedule(league: str, competition: str, team_id: int = TEAM_VFB) -> list[Match]:
    return parse_schedule(get_json(SCHEDULE_URL.format(league=league, team_id=team_id)), competition)
