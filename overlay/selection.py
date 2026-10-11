"""Decides which matches the overlay shows and how often to refresh."""
from datetime import datetime, timedelta

from overlay.model import LIVE_MAX, Match, Status

BEFORE_KICKOFF = timedelta(hours=3)
AFTER_KICKOFF = timedelta(hours=5)
SOON = timedelta(minutes=15)
FAST_INTERVAL = 30
SLOW_INTERVAL = 600


def _is_focus_team(name: str) -> bool:
    if "1860" in name:
        return True
    return "Stuttgart" in name and not name.endswith(" II")


def is_focus(m: Match) -> bool:
    return _is_focus_team(m.home) or _is_focus_team(m.away)


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
