from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum


class Status(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"


# A match not marked finished this long after kickoff is treated as over
# (postponed, or the source never updated it).
LIVE_MAX = timedelta(hours=3)


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


def season_for(d: date) -> int:
    """Season is named after the year it starts in (July)."""
    return d.year if d.month >= 7 else d.year - 1
