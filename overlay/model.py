# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum


class Status(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"


# A match not marked finished this long after kickoff is treated as over
# (postponed, or the source never updated it).
LIVE_MAX = timedelta(hours=3)
# Match.minute during the break; translated only when displayed.
HALF_TIME = "HT"


@dataclass(frozen=True)
class Goal:
    minute: str      # as displayed, e.g. "12'" or "90+2'"
    scorer: str
    home: bool       # counts for the home team (also for own goals)
    penalty: bool = False
    own_goal: bool = False


@dataclass(frozen=True)
class Match:
    competition: str
    home: str
    away: str
    home_goals: int | None
    away_goals: int | None
    status: Status
    kickoff: datetime  # timezone-aware UTC
    minute: str | None = None
    # Details only; not part of a match's identity (goal flashes, stale sets, merging).
    goals: tuple[Goal, ...] = field(default=(), compare=False)
    ref: str | None = field(default=None, compare=False)  # id at goal-api.com


def season_for(d: date) -> int:
    """Season is named after the year it starts in (July)."""
    return d.year if d.month >= 7 else d.year - 1
