# SPDX-License-Identifier: GPL-3.0-or-later
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
    monkeypatch.setattr(ui.subprocess, "Popen", lambda args, **kw: calls.append("popen"))
    ui.run(tmp_path / "config.json")
    assert calls == ["acquire", "mainloop", "release", "popen"]


def test_about_mentions_no_warranty():
    from overlay.ui import about_lines
    assert "Ohne jede Gewährleistung – siehe LICENSE" in about_lines("1.5.0", "Aktuell")


def test_install_click_ignored_while_installing(monkeypatch):
    from overlay import ui
    from overlay.updater import UpdateInfo
    asked, started = [], []
    o = ui.Overlay.__new__(ui.Overlay)
    o.popup = ui.PopupGuard()
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda *a, **k: asked.append(o.popup.active) or True)
    monkeypatch.setattr(ui.threading, "Thread", lambda target, daemon: type("T", (), {"start": lambda self: started.append(1)})())
    o.root = None
    o.update_info = UpdateInfo(True, "1.6.0", None)
    o.installing = False
    o._refresh_update_entry = lambda: None
    o._install_update()
    o._install_update()
    assert (asked, len(started), o.installing, o.popup.active) == ([True], 1, True, False)


def test_status_text_known_update_after_failed_check():
    from overlay.ui import status_text
    from overlay.updater import UpdateInfo
    assert status_text(UpdateInfo(True, "1.6.0", "offline")) == "v1.6.0 verfügbar (letzte Prüfung fehlgeschlagen)"


def test_restart_command_prefers_pythonw_and_detaches(tmp_path):
    import subprocess
    from overlay.ui import restart_command
    (tmp_path / "python.exe").write_text("")
    start = tmp_path / "app" / "start.pyw"
    args, kwargs = restart_command(str(tmp_path / "python.exe"), start)
    assert args == [str(tmp_path / "python.exe"), str(start)]
    assert kwargs == {"creationflags": subprocess.DETACHED_PROCESS}
    (tmp_path / "pythonw.exe").write_text("")
    args, _ = restart_command(str(tmp_path / "python.exe"), start)
    assert args[0] == str(tmp_path / "pythonw.exe")


def test_suffix_marks_scheduled_match_without_update_after_kickoff():
    from datetime import timedelta
    from overlay.ui import format_suffix, is_overdue
    kickoff = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
    m = Match("DFBF", "Stuttgart Frauen", "SGS Essen Frauen", None, None, Status.SCHEDULED, kickoff)
    time = kickoff.astimezone().strftime("%H:%M")
    assert not is_overdue(m, kickoff + timedelta(minutes=10))
    assert format_suffix(m, kickoff + timedelta(minutes=10)) == time
    assert is_overdue(m, kickoff + timedelta(minutes=11))
    assert format_suffix(m, kickoff + timedelta(minutes=11)) == time + "?"


def test_live_and_finished_matches_are_never_overdue():
    from datetime import timedelta
    from overlay.ui import is_overdue
    kickoff = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
    later = kickoff + timedelta(hours=1)
    assert not is_overdue(Match("BL", "A", "B", 0, 0, Status.LIVE, kickoff), later)
    assert not is_overdue(Match("BL", "A", "B", 0, 0, Status.FINISHED, kickoff), later)


def test_popup_guard_is_active_only_while_a_popup_is_open():
    from overlay.ui import PopupGuard
    guard = PopupGuard()
    assert not guard.active
    with guard:
        assert guard.active
        with guard:  # dialog opened from the menu
            assert guard.active
        assert guard.active
    assert not guard.active


def test_popup_guard_releases_on_error():
    import pytest
    from overlay.ui import PopupGuard
    guard = PopupGuard()
    with pytest.raises(RuntimeError):
        with guard:
            raise RuntimeError
    assert not guard.active


def test_texts_in_english():
    from overlay import i18n
    from overlay.model import HALF_TIME
    from overlay.ui import about_lines, format_next, format_suffix, status_text
    from overlay.updater import UpdateInfo
    i18n.set_language("en")
    kickoff = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
    assert status_text(None) == "Not checked yet"
    assert status_text(UpdateInfo(True, "1.6.0", "offline")) == "v1.6.0 available (last check failed)"
    assert status_text(UpdateInfo(False, "1.6.0", None)) == "Up to date"
    assert about_lines("1.6.0", "Up to date")[-1] == "Update: Up to date"
    assert "License: GPL-3.0-or-later" in about_lines("1.6.0", "x")
    assert format_suffix(Match("BL", "A", "B", 1, 1, Status.FINISHED, kickoff), kickoff) == "FT"
    assert format_suffix(Match("BL", "A", "B", 1, 1, Status.LIVE, kickoff, HALF_TIME), kickoff) == "HT"
    m = Match("DFBF", "Stuttgart Frauen", "SGS Essen Frauen", None, None, Status.SCHEDULED, kickoff)
    local = kickoff.astimezone()
    assert format_next(m) == f"Stuttgart Frauen – SGS Essen Frauen · {i18n.short_date(local)} {local:%H:%M}"


def test_half_time_in_german():
    from datetime import timedelta
    from overlay.model import HALF_TIME
    from overlay.ui import format_suffix
    kickoff = datetime(2026, 10, 30, 17, 0, tzinfo=timezone.utc)
    assert format_suffix(Match("BL", "A", "B", 1, 1, Status.LIVE, kickoff, HALF_TIME), kickoff) == "HZ"
    estimated = Match("BL", "A", "B", 1, 1, Status.LIVE, kickoff)
    assert format_suffix(estimated, kickoff + timedelta(minutes=50)) == "HZ"
