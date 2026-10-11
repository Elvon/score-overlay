from datetime import datetime, timedelta

from overlay.model import Match, Status
from overlay.service import ScoreService

NOW = datetime(2026, 10, 11, 12, 0).astimezone()
BL = Match("BL", "A", "B", 0, 0, Status.LIVE, NOW - timedelta(hours=1))
VFB = Match("UCL", "VfB Stuttgart", "C", 1, 0, Status.LIVE, NOW - timedelta(hours=1))


def failing(now):
    raise OSError("network down")


def test_failing_source_isolated():
    service = ScoreService({"a": lambda now: [BL], "b": failing})
    assert service.refresh(NOW) == [BL]


def test_failing_source_keeps_cache():
    calls = []

    def flaky(now):
        calls.append(now)
        if len(calls) > 1:
            raise ValueError("bad json")
        return [VFB]

    service = ScoreService({"b": flaky})
    assert service.refresh(NOW) == [VFB]
    assert service.refresh(NOW) == [VFB]
