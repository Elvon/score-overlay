# SPDX-License-Identifier: GPL-3.0-or-later
from overlay.updater import UpdateInfo, check, is_git_checkout, parse_latest


def test_parse_latest():
    assert parse_latest({"tag_name": "v1.6.0"}) == "1.6.0"
    assert parse_latest({"tag_name": "v1.6.0-beta"}) is None
    assert parse_latest({}) is None


def test_check_finds_newer_release():
    assert check("1.5.0", fetch=lambda url: {"tag_name": "v1.6.0"}) == UpdateInfo(True, "1.6.0", None)


def test_check_same_version_is_not_an_update():
    assert check("1.5.0", fetch=lambda url: {"tag_name": "v1.5.0"}) == UpdateInfo(False, "1.5.0", None)


def test_check_prerelease_tag_is_not_an_update():
    info = check("1.5.0", fetch=lambda url: {"tag_name": "v1.6.0-beta"})
    assert not info.available


def test_check_network_error():
    def fail(url):
        raise OSError("offline")
    info = check("1.5.0", fetch=fail)
    assert not info.available and info.error is not None


def test_is_git_checkout(tmp_path):
    assert not is_git_checkout(tmp_path)
    (tmp_path / ".git").mkdir()
    assert is_git_checkout(tmp_path)


# --- download & install -------------------------------------------------------
import io
import shutil
import zipfile

import pytest

from overlay import updater
from overlay.updater import ARCHIVE_URL, UpdateError, download, install


def make_zip(tmp, files, top="score-overlay"):
    path = tmp / "update.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name if name.startswith("../") else f"{top}/{name}", content)
    return path


NEW = {"start.pyw": "new start", "overlay/__init__.py": '__version__ = "1.6.0"\n', "overlay/ui.py": "new ui"}


def make_app(app):
    app.mkdir()
    (app / "overlay").mkdir()
    (app / "start.pyw").write_text("old start")
    (app / "overlay" / "__init__.py").write_text('__version__ = "1.5.0"\n')
    (app / "old.py").write_text("only in old version")
    (app / "config.json").write_text('{"goal_api_key": "k"}')
    (app / "overlay.log").write_text("log")
    return app


def snapshot(app):
    return {str(p.relative_to(app)): p.read_bytes() for p in sorted(app.rglob("*")) if p.is_file()}


def test_install_replaces_program_keeps_user_files(tmp_path):
    app = make_app(tmp_path / "app")
    install(make_zip(tmp_path, NEW), app, "1.6.0")
    assert "1.6.0" in (app / "overlay" / "__init__.py").read_text()
    assert (app / "overlay" / "ui.py").read_text() == "new ui"
    assert (app / "config.json").read_text() == '{"goal_api_key": "k"}'
    assert (app / "overlay.log").read_text() == "log"
    assert "1.5.0" in (app / ".update-backup" / "overlay" / "__init__.py").read_text()
    assert not (app / "old.py").exists()


@pytest.mark.parametrize("files", [
    {**NEW, "overlay/__init__.py": '__version__ = "1.7.0"\n'},           # wrong version
    {k: v for k, v in NEW.items() if k != "start.pyw"},                    # missing start.pyw
    {**NEW, "../evil.py": "x"},                                            # path traversal
])
def test_install_rejects_bad_archive(tmp_path, files):
    app = make_app(tmp_path / "app")
    before = snapshot(app)
    with pytest.raises(UpdateError):
        install(make_zip(tmp_path, files), app, "1.6.0")
    assert snapshot(app) == before
    assert not (tmp_path / "evil.py").exists()


def test_install_refuses_git_checkout(tmp_path):
    app = make_app(tmp_path / "app")
    (app / ".git").mkdir()
    before = snapshot(app)
    with pytest.raises(UpdateError):
        install(make_zip(tmp_path, NEW), app, "1.6.0")
    assert snapshot(app) == before


def test_install_rolls_back_on_copy_error(tmp_path, monkeypatch):
    app = make_app(tmp_path / "app")
    before = snapshot(app)
    real_copy = shutil.copy2
    calls = []

    def flaky_copy(src, dst, *args, **kwargs):
        calls.append(src)
        if len(calls) > 1 and "update-backup" not in str(dst):
            raise OSError("disk full")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(updater.shutil, "copy2", flaky_copy)
    with pytest.raises(UpdateError):
        install(make_zip(tmp_path, NEW), app, "1.6.0")
    monkeypatch.undo()
    assert {k: v for k, v in snapshot(app).items() if not k.startswith(".update-backup")} == before


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_writes_zip(tmp_path):
    payload = make_zip(tmp_path, NEW).read_bytes()
    urls = []
    path = download("1.6.0", tmp_path, opener=lambda url, timeout=None: urls.append(url) or FakeResponse(payload))
    assert zipfile.is_zipfile(path)
    assert urls == [ARCHIVE_URL.format(version="1.6.0")]


def test_download_rejects_non_zip(tmp_path):
    with pytest.raises(UpdateError):
        download("1.6.0", tmp_path, opener=lambda url, timeout=None: FakeResponse(b"<html>"))


def test_download_wraps_network_error(tmp_path):
    def fail(url, timeout=None):
        raise OSError("offline")
    with pytest.raises(UpdateError):
        download("1.6.0", tmp_path, opener=fail)
