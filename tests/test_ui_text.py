from datetime import datetime, timezone

from overlay.model import Match, Status
from overlay.ui import format_next


def test_format_next_uses_local_german_weekday_and_date():
    kickoff = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    m = Match("UCL", "VfB Stuttgart", "Atlético Madrid", None, None, Status.SCHEDULED, kickoff)
    local = kickoff.astimezone()
    weekday = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][local.weekday()]
    assert format_next(m) == f"VfB Stuttgart – Atlético Madrid · {weekday} {local:%d.%m. %H:%M}"


def test_suffix_estimates_minute_when_source_has_none():
    from datetime import timedelta
    from overlay.ui import format_suffix
    kickoff = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)
    m = Match("BL", "A", "B", 1, 0, Status.LIVE, kickoff)
    assert format_suffix(m, kickoff + timedelta(minutes=20)) == "~21'"


def test_suffix_keeps_reported_minute():
    from overlay.ui import format_suffix
    kickoff = datetime(2026, 10, 17, 13, 30, tzinfo=timezone.utc)
    m = Match("UCL", "A", "B", 1, 0, Status.LIVE, kickoff, "67'")
    assert format_suffix(m, kickoff) == "67'"


def test_score_marks_stale():
    from overlay.ui import format_score
    m = Match("BL", "A", "B", 2, 1, Status.LIVE, datetime(2026, 10, 17, tzinfo=timezone.utc))
    assert format_score(m, stale=False) == "2:1"
    assert format_score(m, stale=True) == "2:1?"


def test_about_lines():
    from overlay.ui import REPO_URL, about_lines
    lines = about_lines("1.5.0", "Aktuell")
    assert "Version 1.5.0" in lines
    assert "Lizenz: GPL-3.0-or-later" in lines
    assert REPO_URL in lines
    assert "Update: Aktuell" in lines


def test_status_text():
    from overlay.ui import status_text
    from overlay.updater import UpdateInfo
    assert status_text(None) == "Noch nicht geprüft"
    assert status_text(UpdateInfo(True, "1.6.0", None)) == "v1.6.0 verfügbar"
    assert status_text(UpdateInfo(False, None, "offline")) == "Prüfung fehlgeschlagen"
    assert status_text(UpdateInfo(False, "1.5.0", None)) == "Aktuell"


def test_restart_releases_lock_before_spawning(monkeypatch, tmp_path):
    from overlay import ui
    calls = []

    class FakeRoot:
        def mainloop(self):
            calls.append("mainloop")

    class FakeOverlay:
        def __init__(self, config_path):
            self.root = FakeRoot()
            self.restart_requested = True

    monkeypatch.setattr(ui, "Overlay", FakeOverlay)
    monkeypatch.setattr(ui.single_instance, "acquire", lambda name: calls.append("acquire") or 1)
    monkeypatch.setattr(ui.single_instance, "release", lambda lock: calls.append("release"))
    monkeypatch.setattr(ui.subprocess, "Popen", lambda args: calls.append("popen"))
    ui.run(tmp_path / "config.json")
    assert calls == ["acquire", "mainloop", "release", "popen"]
