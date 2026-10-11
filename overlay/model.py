from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Status(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"


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
