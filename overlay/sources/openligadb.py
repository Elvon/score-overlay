"""OpenLigaDB: Bundesliga (bl1), DFB-Pokal (dfb), Frauen-Bundesliga (ffb1)."""
from datetime import datetime

from overlay.model import Match, Status, season_for
from overlay.sources.http import get_json

URL = "https://api.openligadb.de/getmatchdata/{league}/{season}"


def _parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _score(m: dict) -> tuple[int, int] | None:
    results = m.get("matchResults") or []
    if results:
        r = max(results, key=lambda r: r.get("resultOrderID", 0))
        return r["pointsTeam1"], r["pointsTeam2"]
    goals = m.get("goals") or []
    if goals:
        return goals[-1]["scoreTeam1"], goals[-1]["scoreTeam2"]
    return None


def parse(data: list[dict], competition: str, now: datetime) -> list[Match]:
    matches = []
    for m in data:
        kickoff = _parse_time(m["matchDateTimeUTC"])
        if kickoff.year < 2000:  # placeholder for unscheduled matches
            continue
        if m.get("matchIsFinished"):
            status = Status.FINISHED
        elif kickoff <= now:
            status = Status.LIVE
        else:
            status = Status.SCHEDULED
        score = _score(m)
        if score is None and status is not Status.SCHEDULED:
            score = (0, 0)
        if status is Status.SCHEDULED:
            score = None
        matches.append(Match(
            competition=competition,
            home=m["team1"]["teamName"],
            away=m["team2"]["teamName"],
            home_goals=score[0] if score else None,
            away_goals=score[1] if score else None,
            status=status,
            kickoff=kickoff,
        ))
    return matches


def fetch(league: str, competition: str, now: datetime) -> list[Match]:
    data = get_json(URL.format(league=league, season=season_for(now.date())))
    return parse(data, competition, now)
