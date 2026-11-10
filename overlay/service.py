# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetches all sources, isolating failures and caching the last good result."""
import logging
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Callable

from overlay.model import Goal, Match, Status
from overlay.selection import DEFAULT_LEAGUES, SLOW_INTERVAL, is_hot, select
from overlay.sources import espn, goalapi, openligadb, thesportsdb

Fetcher = Callable[[datetime], list[Match]]
LiveFetcher = Callable[[str, datetime], list[Match]]  # (competition, now) -> today's matches
GoalsFetcher = Callable[[str], tuple[Goal, ...]]  # goal-api fixture id -> its goals

LIVE_COMPETITIONS = ("BL", "DFB", "DFBF", "FBL", "RLB")
# Regular source of each live competition: while it has never answered, goal-api.com is asked anyway.
LIVE_SOURCES = {"BL": "bl1", "DFB": "dfb", "FBL": "ffb1"}
# goal-api.com has no live coverage here: matches stay SCHEDULED during play, the result comes afterwards.
NO_LIVE_DATA = frozenset({"DFBF"})
RETRY_SECONDS = 60  # retry interval for a source that has not answered once since the start
TEAM_SCHEDULE_EVERY = timedelta(hours=1)
LIVE_FAST = timedelta(minutes=1)    # while a match of the competition is live
LIVE_SLOW = timedelta(minutes=30)   # matches today, none live
LIVE_GIVE_UP = timedelta(minutes=5)  # then fall back to the regular sources
GOALS_RETRIES = 5  # goal requests per score while goal-api.com lists fewer goals than the score
log = logging.getLogger(__name__)


def throttled(fetch: Fetcher, interval: timedelta) -> Fetcher:
    """Calls fetch at most once per interval and returns the cached result in between."""
    state: dict = {}

    def wrapper(now: datetime) -> list[Match]:
        last = state.get("at")
        if last is None or now - last >= interval:
            state["at"] = now  # also after a failure: retry only after the interval
            state["result"] = fetch(now)
        return state.get("result", [])

    return wrapper


def default_fetchers(goal_api_key: str | None = None) -> dict[str, Fetcher]:
    def espn_today(league: str, comp: str) -> Fetcher:
        return lambda now: espn.fetch(league, comp, now.astimezone().date())

    fetchers = {
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
    if goal_api_key:
        # Covers competitions the free sources lack, e.g. the women's DFB-Pokal.
        fetchers["vfb_women_schedule"] = throttled(
            lambda now: goalapi.fetch_team(goalapi.TEAM_VFB_WOMEN, goal_api_key), TEAM_SCHEDULE_EVERY)
    return fetchers


def goal_api_live_fetch(key: str) -> LiveFetcher:
    return lambda comp, now: goalapi.fetch(comp, now.astimezone().date(), key, now)


def goal_api_goals_fetch(key: str) -> GoalsFetcher:
    return lambda ref: goalapi.fetch_goals(ref, key)


def _today(m: Match, now: datetime) -> bool:
    return m.kickoff.astimezone().date() == now.astimezone().date()


class ScoreService:
    def __init__(self, fetchers: dict[str, Fetcher] | None = None,
                 live_fetch: LiveFetcher | None = None, goals_fetch: GoalsFetcher | None = None):
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
        # goal-api.com goals per fixture id: (score total, goals, requests for that total).
        self.goals_fetch = goals_fetch
        self.goal_details: dict[str, tuple[int, tuple[Goal, ...], int]] = {}

    def _never_answered(self, key: str | None) -> bool:
        return key in self.failed and key not in self.cache

    def wait(self, interval: int) -> int:
        """Seconds until the next refresh; short while a source has not answered once."""
        if any(self._never_answered(key) for key in self.fetchers):
            return min(interval, RETRY_SECONDS)
        return interval

    def _due(self, key: str, now: datetime) -> bool:
        last = self.last_fetch.get(key)
        if last is None or now - last >= timedelta(seconds=SLOW_INTERVAL):
            return True
        if self._never_answered(key):
            return now - last >= timedelta(seconds=RETRY_SECONDS)
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

    def _drop_live(self, comp: str) -> None:
        for m in self.live.pop(comp, None) or []:
            self.goal_details.pop(m.ref, None)

    def _with_goals(self, matches: list[Match]) -> list[Match]:
        """Attaches goal-api.com goals, asking again only when the score changed."""
        if self.goals_fetch is None:
            return matches
        result = []
        for m in matches:
            total = (m.home_goals or 0) + (m.away_goals or 0)
            if m.ref is None or total == 0:
                result.append(m)
                continue
            known, goals, tries = self.goal_details.get(m.ref, (None, (), 0))
            if known != total:
                tries = 0
            if known != total or (len(goals) < total and tries < GOALS_RETRIES):
                try:
                    goals = self.goals_fetch(m.ref)
                    self.goal_details[m.ref] = (total, goals, tries + 1)
                except Exception:  # counts as a try: a broken fixture must not eat the daily quota
                    log.warning("goals for %s failed", m.ref, exc_info=True)
                    self.goal_details[m.ref] = (total, goals, tries + 1)
            result.append(replace(m, goals=goals))
        return result

    def _refresh_live(self, now: datetime) -> None:
        base = self._base_matches()
        for comp in LIVE_COMPETITIONS:
            def todays(matches: list[Match]) -> list[Match]:
                return [m for m in matches
                        if m.competition == comp and (_today(m, now) or m.status is Status.LIVE)]

            cached = self.live.get(comp)
            unknown = self._never_answered(LIVE_SOURCES.get(comp))  # e.g. OpenLigaDB down since the start
            if not todays(base) and not todays(cached or []) and not unknown:
                self._drop_live(comp)  # matchday over
                continue
            # Once goal-api answered, trust its view of what is live.
            current = todays(cached) if cached is not None else todays(base)
            hot = comp not in NO_LIVE_DATA and any(is_hot(m, now) for m in current)
            interval = LIVE_FAST if hot else LIVE_SLOW
            last = self.live_tried.get(comp)
            if last is not None and now - last < interval:
                continue
            self.live_tried[comp] = now
            try:
                self.live[comp] = self._with_goals(self.live_fetch(comp, now))
                self.live_ok[comp] = now
                self.live_failed.discard(comp)
            except Exception:
                log.warning("live source failed for %s", comp, exc_info=True)
                self.live_failed.add(comp)
                ok = self.live_ok.get(comp)
                if ok is None or now - ok > LIVE_GIVE_UP:
                    self._drop_live(comp)
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
