"""Estimates the match minute for sources that do not report one."""
from datetime import datetime

FIRST_HALF = 45
FIRST_HALF_END = 48      # incl. typical stoppage time
SECOND_HALF_START = 63   # after a 15 minute break
SECOND_HALF_END = SECOND_HALF_START + 45


def estimate_minute(kickoff: datetime, now: datetime) -> str:
    elapsed = max(0.0, (now - kickoff).total_seconds() / 60)
    if elapsed < FIRST_HALF:
        return f"~{int(elapsed) + 1}'"
    if elapsed < FIRST_HALF_END:
        return "~45+'"
    if elapsed < SECOND_HALF_START:
        return "HZ"
    if elapsed < SECOND_HALF_END:
        return f"~{46 + int(elapsed - SECOND_HALF_START)}'"
    return "~90+'"
