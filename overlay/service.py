"""Fetches all sources, isolating failures and caching the last good result."""
import logging
from datetime import datetime, timedelta
from typing import Callable

from overlay.model import Match, Status
from overlay.selection import DEFAULT_LEAGUES, SLOW_INTERVAL, is_hot, select
from overlay.sources import espn, goalapi, openligadb, thesportsdb

Fetcher = Callable[[datetime], list[Match]]
LiveFetcher = Callable[[str, datetime], list[Match]]  # (competition, now) -> today's matches

LIVE_COMPETITIONS = ("BL", "DFB", "FBL", "RLB")
LIVE_FAST = timedelta(minutes=1)    # while a match of the competition is live
LIVE_SLOW = timedelta(minutes=30)   # matches today, none live
LIVE_GIVE_UP = timedelta(minutes=5)  # then fall back to the regular sources
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


def goal_api_live_fetch(key: str) -> LiveFetcher:
    return lambda comp, now: goalapi.fetch(comp, now.astimezone().date(), key)


def _today(m: Match, now: datetime) -> bool:
    return m.kickoff.astimezone().date() == now.astimezone().date()


class ScoreService:
    def __init__(self, fetchers: dict[str, Fetcher] | None = None,
                 live_fetch: LiveFetcher | None = None):
        self.fetchers = fetchers if fetchers is not None else default_fetchers()
        self.cache: dict[str, list[Match]] = {}
        self.last_fetch: dict[str, datetime] = {}
        self.shown: list[Match] = []
        self._now = datetime.now().astimezone()
        self.leagues: frozenset[str] = DEFAULT_LEAGUES
        self.failed: set[str] = set()
        # Optional live source (goal-api.com); replaces today's matches per competition.
        self.live_fetch = live_fetch
        self.live: dict[str, list[Match]] = {}
        self.live_tried: dict[str, datetime] = {}
        self.live_ok: dict[str, datetime] = {}
        self.live_failed: set[str] = set()

    def _due(self, key: str, now: datetime) -> bool:
        last = self.last_fetch.get(key)
        if last is None or now - last >= timedelta(seconds=SLOW_INTERVAL):
            return True
        # Fast cycle: only sources with a live/imminent match currently on screen.
        return any(m in self.shown and is_hot(m, now) for m in self.cache.get(key, []))

    def stale_matches(self) -> set[Match]:
        """Cached matches of sources whose latest fetch failed."""
        stale = {m for key in self.failed for m in self.cache.get(key, [])}
        return stale | {m for comp in self.live_failed for m in self.live.get(comp, [])}

    def _base_matches(self) -> list[Match]:
        return [m for ms in self.cache.values() for m in ms]

    def all_matches(self) -> list[Match]:
        live = [m for ms in self.live.values() for m in ms]
        replaced = [m for m in self._base_matches()
                    if not (m.competition in self.live and _today(m, self._now))]
        return live + replaced

    def _refresh_live(self, now: datetime) -> None:
        base = self._base_matches()
        for comp in LIVE_COMPETITIONS:
            def todays(matches: list[Match]) -> list[Match]:
                return [m for m in matches
                        if m.competition == comp and (_today(m, now) or m.status is Status.LIVE)]

            cached = self.live.get(comp)
            if not todays(base) and not todays(cached or []):
                self.live.pop(comp, None)  # matchday over
                continue
            # Once goal-api answered, trust its view of what is live.
            current = todays(cached) if cached is not None else todays(base)
            interval = LIVE_FAST if any(is_hot(m, now) for m in current) else LIVE_SLOW
            last = self.live_tried.get(comp)
            if last is not None and now - last < interval:
                continue
            self.live_tried[comp] = now
            try:
                self.live[comp] = self.live_fetch(comp, now)
                self.live_ok[comp] = now
                self.live_failed.discard(comp)
            except Exception:
                log.warning("live source failed for %s", comp, exc_info=True)
                self.live_failed.add(comp)
                ok = self.live_ok.get(comp)
                if ok is None or now - ok > LIVE_GIVE_UP:
                    self.live.pop(comp, None)
                    self.live_failed.discard(comp)

    def refresh(self, now: datetime) -> list[Match]:
        for key, fetch in self.fetchers.items():
            if not self._due(key, now):
                continue
            self.last_fetch[key] = now
            try:
                self.cache[key] = fetch(now)
                self.failed.discard(key)
            except Exception:  # one broken source must not hide the others
                self.failed.add(key)
                log.warning("source %s failed", key, exc_info=True)
        self._now = now
        if self.live_fetch is not None:
            self._refresh_live(now)
        self.shown = select(self.all_matches(), now, self.leagues)
        return self.shown
