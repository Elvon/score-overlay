# SPDX-License-Identifier: GPL-3.0-or-later
"""Decides which matches the overlay shows and how often to refresh."""
from datetime import datetime, timedelta

from overlay.model import LIVE_MAX, Match, Status

BEFORE_KICKOFF = timedelta(hours=3)
AFTER_KICKOFF = timedelta(hours=5)
SOON = timedelta(minutes=15)
FAST_INTERVAL = 30
SLOW_INTERVAL = 600


TEAMS = ["VfB", "VfB Frauen", "1860"]
# Display order of non-focus matches; unlisted competitions come last.
COMPETITION_ORDER = {"BL": 0, "UCL": 1}
DEFAULT_LEAGUES = frozenset({"BL"})


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


def _shown(m: Match, now: datetime, leagues: frozenset[str]) -> bool:
    if is_focus(m) and (m.status is Status.LIVE
                        or m.kickoff - BEFORE_KICKOFF <= now <= m.kickoff + AFTER_KICKOFF):
        return True
    if m.competition not in leagues:
        return False
    return m.status is Status.LIVE or m.kickoff.astimezone().date() == now.astimezone().date()


def select(matches: list[Match], now: datetime,
           leagues: frozenset[str] = DEFAULT_LEAGUES) -> list[Match]:
    """leagues: competitions whose non-focus matches of the day are shown."""
    seen = set()
    result = []
    for m in matches:
        # A focus team plays at most once a day; this also merges the same match
        # reported by two sources under different names ("TSV 1860 München" / "1860 Munich").
        day = m.kickoff.astimezone().date()
        key = (frozenset(_teams(m)), day) if is_focus(m) else (m.home, m.away, day)
        if key in seen or not _shown(m, now, leagues):
            continue
        seen.add(key)
        result.append(m)
    def order(m: Match) -> tuple:
        if is_focus(m):
            return (0, 0, m.kickoff)
        return (1, COMPETITION_ORDER.get(m.competition, len(COMPETITION_ORDER)), m.kickoff)

    return sorted(result, key=order)


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
