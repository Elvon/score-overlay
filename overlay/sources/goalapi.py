# SPDX-License-Identifier: GPL-3.0-or-later
"""goal-api.com (needs a free API key): reliable live scores for today's matches."""
from datetime import date, datetime

from overlay.model import HALF_TIME, Goal, Match, Status
from overlay.sources.http import get_json

BASE = "https://api.goal-api.com/v1"
# goal-api league ids per overlay competition code.
LEAGUES = {
    "BL": "cmr77dvgm0002rx06rt2uqxii",
    "DFB": "cmr77dvgm0003rx06nnbqia6t",
    "FBL": "cmr77dvgm0008rx06s61intpw",
    "DFBF": "cmr77dvgm0007rx06a1p4k59q",  # DFB-Pokal der Frauen
    "RLB": "cmr77dvgm000arx06ghs089wq",  # all Regionalliga divisions
}
TEAM_VFB_WOMEN = "cmr79ja8003yarx06fupnwezx"
# goal-api league names (prefix before " - <round>") -> overlay competition code
COMPETITIONS_BY_NAME = {
    "Bundesliga": "BL",
    "DFB Pokal": "DFB",
    "DFB Pokal Women": "DFBF",
    "Frauen Bundesliga": "FBL",
    "Regionalliga": "RLB",
}
LIVE_PERIODS = {"FIRST_HALF", "SECOND_HALF", "EXTRA_TIME", "PENALTIES"}
OWN_GOAL = " (o.g.)"


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
            status, minute = Status.LIVE, HALF_TIME
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
            ref=f.get("id"),
        ))
    return matches


def _order(event: dict) -> tuple[int, int]:
    """Match order from "time" ("45+2" -> (45, 2)); timeNum is missing for some goals."""
    base, _, extra = str(event.get("time") or "").partition("+")
    try:
        return int(base), int(extra or 0)
    except ValueError:
        num = event.get("timeNum")
        return (num, 0) if isinstance(num, int) else (999, 0)


def parse_goals(events: list[dict]) -> tuple[Goal, ...]:
    """Goals from a fixture's events, in match order."""
    goals = sorted((e for e in events if e.get("type") == "GOAL"), key=_order)
    result = []
    for e in goals:
        home = e.get("homeScorer") is not None
        name = (e.get("homeScorer") if home else e.get("awayScorer")) or ""
        own_goal = name.endswith(OWN_GOAL)
        result.append(Goal(
            minute=f"{e['time']}'" if e.get("time") else "",
            scorer=name.removesuffix(OWN_GOAL) or "?",
            home=home,
            penalty=e.get("info") == "Penalty",
            own_goal=own_goal,
        ))
    return tuple(result)


def fetch_goals(fixture_id: str, key: str) -> tuple[Goal, ...]:
    data = get_json(f"{BASE}/fixtures/{fixture_id}/events", headers={"Authorization": f"Bearer {key}"})
    return parse_goals(data["data"] if isinstance(data, dict) else data)


def fetch(competition: str, day: date, key: str) -> list[Match]:
    url = f"{BASE}/fixtures/date/{day:%Y-%m-%d}?leagueId={LEAGUES[competition]}&limit=100"
    return parse(get_json(url, headers={"Authorization": f"Bearer {key}"})["data"], competition)


def competition_of(league_name: str) -> str | None:
    return COMPETITIONS_BY_NAME.get(league_name.split(" - ")[0].strip())


def parse_team(fixtures: list[dict]) -> list[Match]:
    """A team's fixtures across competitions; unknown competitions are skipped."""
    matches = []
    for f in fixtures:
        comp = competition_of(f.get("leagueName") or "")
        if comp:
            matches.extend(parse([f], comp))
    return matches


def fetch_team(team_id: str, key: str) -> list[Match]:
    url = f"{BASE}/teams/{team_id}/fixtures?limit=100"
    return parse_team(get_json(url, headers={"Authorization": f"Bearer {key}"})["data"])
