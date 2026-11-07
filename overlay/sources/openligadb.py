# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenLigaDB: Bundesliga (bl1), DFB-Pokal (dfb), Frauen-Bundesliga (ffb1)."""
from datetime import datetime

from overlay.model import LIVE_MAX, Goal, Match, Status, season_for
from overlay.sources.http import get_json

URL = "https://api.openligadb.de/getmatchdata/{league}/{season}"


def _parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _score(m: dict) -> tuple[int, int] | None:
    results = m.get("matchResults") or []
    goals = m.get("goals") or []
    # While running, goals are entered before the result rows are updated.
    if goals and (not m.get("matchIsFinished") or not results):
        g = max(goals, key=lambda g: g["scoreTeam1"] + g["scoreTeam2"])
        return g["scoreTeam1"], g["scoreTeam2"]
    if results:
        r = max(results, key=lambda r: r.get("resultOrderID", 0))
        return r["pointsTeam1"], r["pointsTeam2"]
    return None


def _goals(m: dict) -> tuple[Goal, ...]:
    goals = []
    before = 0
    for g in sorted(m.get("goals") or [], key=lambda g: g["scoreTeam1"] + g["scoreTeam2"]):
        minute = g.get("matchMinute")
        goals.append(Goal(
            minute=f"{minute}'" if minute is not None else "",
            scorer=g.get("goalGetterName") or "?",
            home=g["scoreTeam1"] > before,
            penalty=bool(g.get("isPenalty")),
            own_goal=bool(g.get("isOwnGoal")),
        ))
        before = g["scoreTeam1"]
    return tuple(goals)


def parse(data: list[dict], competition: str, now: datetime) -> list[Match]:
    matches = []
    for m in data:
        kickoff = _parse_time(m["matchDateTimeUTC"])
        if kickoff.year < 2000:  # placeholder for unscheduled matches
            continue
        if m.get("matchIsFinished") or now > kickoff + LIVE_MAX:
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
            goals=() if status is Status.SCHEDULED else _goals(m),
        ))
    return matches


def fetch(league: str, competition: str, now: datetime) -> list[Match]:
    data = get_json(URL.format(league=league, season=season_for(now.date())))
    return parse(data, competition, now)
