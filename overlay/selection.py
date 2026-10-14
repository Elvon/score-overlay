"""Decides which matches the overlay shows and how often to refresh."""
from datetime import datetime, timedelta

from overlay.model import LIVE_MAX, Match, Status

BEFORE_KICKOFF = timedelta(hours=3)
AFTER_KICKOFF = timedelta(hours=5)
SOON = timedelta(minutes=15)
FAST_INTERVAL = 30
SLOW_INTERVAL = 600


TEAMS = ["VfB", "VfB Frauen", "1860"]


def team_of(name: str) -> str | None:
    """Which focus team a source's team name belongs to, if any."""
    if "1860" in name:
        return "1860"
    if "Stuttgart" in name and not name.endswith(" II"):
        return "VfB Frauen" if "Frauen" in name else "VfB"
    return None


def _teams(m: Match) -> set[str]:
    return {t for t in (team_of(m.home), team_of(m.away)) if t}


def is_focus(m: Match) -> bool:
    return bool(_teams(m))


def _shown(m: Match, now: datetime) -> bool:
    focus = is_focus(m)
    if m.status is Status.LIVE and (focus or m.competition == "BL"):
        return True
    if m.competition == "BL" and m.kickoff.astimezone().date() == now.astimezone().date():
        return True
    return focus and m.kickoff - BEFORE_KICKOFF <= now <= m.kickoff + AFTER_KICKOFF


def select(matches: list[Match], now: datetime) -> list[Match]:
    seen = set()
    result = []
    for m in matches:
        key = (m.home, m.away, m.kickoff.date())
        if key in seen or not _shown(m, now):
            continue
        seen.add(key)
        result.append(m)
    return sorted(result, key=lambda m: (not is_focus(m), m.kickoff))


def is_hot(m: Match, now: datetime) -> bool:
    """Live, or a focus match about to start / overdue to be reported as started."""
    if m.status is Status.LIVE:
        return True
    return is_focus(m) and m.status is Status.SCHEDULED and -LIVE_MAX <= m.kickoff - now <= SOON


def next_interval(shown: list[Match], now: datetime) -> int:
    return FAST_INTERVAL if any(is_hot(m, now) for m in shown) else SLOW_INTERVAL


def next_matches(all_matches: list[Match], shown: list[Match], now: datetime) -> list[tuple[str, Match]]:
    """Next upcoming match per focus team that has nothing on screen right now."""
    busy = set().union(*(_teams(m) for m in shown)) if shown else set()
    result = []
    for team in TEAMS:
        if team in busy:
            continue
        upcoming = [m for m in all_matches
                    if team in _teams(m) and m.status is Status.SCHEDULED and m.kickoff > now]
        if upcoming:
            result.append((team, min(upcoming, key=lambda m: m.kickoff)))
    return result
