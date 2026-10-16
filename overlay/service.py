"""Fetches all sources, isolating failures and caching the last good result."""
import logging
from datetime import datetime, timedelta
from typing import Callable

from overlay.model import Match
from overlay.selection import DEFAULT_LEAGUES, SLOW_INTERVAL, is_hot, select
from overlay.sources import espn, openligadb, thesportsdb

Fetcher = Callable[[datetime], list[Match]]
log = logging.getLogger(__name__)


def default_fetchers() -> dict[str, Fetcher]:
    def espn_today(league: str, comp: str) -> Fetcher:
        return lambda now: espn.fetch(league, comp, now.astimezone().date())

    return {
        "bl1": lambda now: openligadb.fetch("bl1", "BL", now),
        "dfb": lambda now: openligadb.fetch("dfb", "DFB", now),
        "ffb1": lambda now: openligadb.fetch("ffb1", "FBL", now),
        "ucl": espn_today("uefa.champions", "UCL"),
        "uel": espn_today("uefa.europa", "UEL"),
        "uecl": espn_today("uefa.europa.conf", "UECL"),
        # Upcoming VfB international matches for the "next match" line.
        "vfb_ucl_schedule": lambda now: espn.fetch_schedule("uefa.champions", "UCL"),
        "1860": lambda now: thesportsdb.fetch(),
    }


class ScoreService:
    def __init__(self, fetchers: dict[str, Fetcher] | None = None):
        self.fetchers = fetchers if fetchers is not None else default_fetchers()
        self.cache: dict[str, list[Match]] = {}
        self.last_fetch: dict[str, datetime] = {}
        self.shown: list[Match] = []
        self.leagues: frozenset[str] = DEFAULT_LEAGUES

    def _due(self, key: str, now: datetime) -> bool:
        last = self.last_fetch.get(key)
        if last is None or now - last >= timedelta(seconds=SLOW_INTERVAL):
            return True
        # Fast cycle: only sources with a live/imminent match currently on screen.
        return any(m in self.shown and is_hot(m, now) for m in self.cache.get(key, []))

    def all_matches(self) -> list[Match]:
        return [m for ms in self.cache.values() for m in ms]

    def refresh(self, now: datetime) -> list[Match]:
        for key, fetch in self.fetchers.items():
            if not self._due(key, now):
                continue
            self.last_fetch[key] = now
            try:
                self.cache[key] = fetch(now)
            except Exception:  # one broken source must not hide the others
                log.warning("source %s failed", key, exc_info=True)
        self.shown = select(self.all_matches(), now, self.leagues)
        return self.shown
