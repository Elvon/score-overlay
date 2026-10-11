"""Decides which matches the overlay shows and how often to refresh."""
from datetime import datetime, timedelta

from overlay.model import Match, Status

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


def next_interval(shown: list[Match], now: datetime) -> int:
    for m in shown:
        if m.status is Status.LIVE:
            return FAST_INTERVAL
        if is_focus(m) and m.status is Status.SCHEDULED and timedelta(0) <= m.kickoff - now <= SOON:
            return FAST_INTERVAL
    return SLOW_INTERVAL
