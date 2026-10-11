from overlay.config import DEFAULTS, load, save


def test_load_missing_returns_defaults(tmp_path):
    assert load(tmp_path / "config.json") == DEFAULTS


def test_load_corrupt_returns_defaults(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{", encoding="utf-8")
    assert load(p) == DEFAULTS


def test_save_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    save(p, {"right": 3000, "y": 20})
    assert load(p) == {"right": 3000, "y": 20}


def test_defaults_anchor_right_edge():
    assert DEFAULTS == {"right": None, "y": 10}
