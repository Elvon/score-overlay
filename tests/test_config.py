# SPDX-License-Identifier: GPL-3.0-or-later
from overlay.config import DEFAULTS, load, on_screen, save


def test_load_missing_returns_defaults(tmp_path):
    assert load(tmp_path / "config.json") == DEFAULTS


def test_load_corrupt_returns_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{", encoding="utf-8")
    assert load(p) == DEFAULTS


def test_save_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    save(p, {"right": 3000, "y": 20})
    assert load(p) == {**DEFAULTS, "right": 3000, "y": 20}


def test_defaults_anchor_right_edge():
    assert DEFAULTS == {"right": None, "y": 10, "sound": True,
                        "preview": True, "all_bl": True, "all_ucl": False,
                        "sound_file": r"C:\Windows\Media\tada.wav"}


def test_position_on_screen_kept():
    # virtual desktop spanning a left monitor: x from -1920 to 1920, y 0..1080
    assert on_screen({"right": -10, "y": 10}, (-1920, 0, 3840, 1080))


def test_position_off_screen_rejected():
    assert not on_screen({"right": 5000, "y": 10}, (0, 0, 1920, 1080))
    assert not on_screen({"right": 1900, "y": 2000}, (0, 0, 1920, 1080))
    assert not on_screen({"right": "x", "y": None}, (0, 0, 1920, 1080))


def test_default_position_counts_as_on_screen():
    assert on_screen({"right": None, "y": 10}, (0, 0, 1920, 1080))


def test_sound_defaults_on(tmp_path):
    assert load(tmp_path / "missing.json")["sound"] is True


def test_old_config_without_sound_gets_default(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"right": 100, "y": 5}', encoding="utf-8")
    assert load(p) == {**DEFAULTS, "right": 100, "y": 5}


def test_display_switch_defaults(tmp_path):
    cfg = load(tmp_path / "missing.json")
    assert (cfg["preview"], cfg["all_bl"], cfg["all_ucl"]) == (True, True, False)


def test_leagues_from_config():
    from overlay.config import leagues
    assert leagues({"all_bl": True, "all_ucl": False}) == frozenset({"BL"})
    assert leagues({"all_bl": False, "all_ucl": True}) == frozenset({"UCL"})


def test_goal_sound_file_defaults_to_tada(tmp_path):
    assert load(tmp_path / "missing.json")["sound_file"] == r"C:\Windows\Media\tada.wav"


def test_save_keeps_entries_it_does_not_manage(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"goal_api_key": "secret", "right": 1, "y": 2}', encoding="utf-8")
    save(p, {"right": 50, "y": 60})
    assert load(p)["goal_api_key"] == "secret"
    assert (load(p)["right"], load(p)["y"]) == (50, 60)


def test_ui_settings_only_contains_overlay_entries():
    from overlay.config import ui_settings
    cfg = {**DEFAULTS, "goal_api_key": "secret", "right": 5}
    assert "goal_api_key" not in ui_settings(cfg)
    assert ui_settings(cfg)["right"] == 5
