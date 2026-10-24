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
