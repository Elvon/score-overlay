"""Fetches all sources, isolating failures and caching the last good result."""
import logging
from datetime import datetime
from typing import Callable

from overlay.model import Match
from overlay.selection import select
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
        "1860": lambda now: thesportsdb.fetch(),
    }


class ScoreService:
    def __init__(self, fetchers: dict[str, Fetcher] | None = None):
        self.fetchers = fetchers if fetchers is not None else default_fetchers()
        self.cache: dict[str, list[Match]] = {}

    def refresh(self, now: datetime) -> list[Match]:
        for key, fetch in self.fetchers.items():
            try:
                self.cache[key] = fetch(now)
            except Exception:  # one broken source must not hide the others
                log.warning("source %s failed", key, exc_info=True)
        return select([m for ms in self.cache.values() for m in ms], now)
