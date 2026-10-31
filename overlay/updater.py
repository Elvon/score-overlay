# SPDX-License-Identifier: GPL-3.0-or-later
"""Self-update from Codeberg releases."""
import logging
import re
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from overlay.i18n import t
from overlay.sources.http import get_json
from overlay.version import is_newer, parse_version

RELEASE_URL = "https://codeberg.org/api/v1/repos/ElvonMF/score-overlay/releases/latest"
ARCHIVE_URL = "https://codeberg.org/ElvonMF/score-overlay/archive/v{version}.zip"

# Never touched by an update.
PRESERVED = {"config.json", "overlay.log", ".update-backup", ".git"}
BACKUP_DIR = ".update-backup"
DOWNLOAD_TIMEOUT = 30
ALLOWED_HOST = "codeberg.org"
_install_lock = threading.Lock()

log = logging.getLogger(__name__)


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    version: str | None
    error: str | None


def parse_latest(release: dict) -> str | None:
    """Version of the latest release, or None if its tag is not a plain vX.Y.Z."""
    tag = release.get("tag_name") or ""
    try:
        return ".".join(str(n) for n in parse_version(tag))
    except ValueError:
        return None


def check(current: str, fetch=get_json) -> UpdateInfo:
    try:
        latest = parse_latest(fetch(RELEASE_URL))
    except Exception as exc:  # network, HTTP, JSON
        log.warning("update check failed", exc_info=True)
        return UpdateInfo(False, None, str(exc) or type(exc).__name__)
    if latest is None:
        return UpdateInfo(False, None, None)
    return UpdateInfo(is_newer(latest, current), latest, None)


def merge_info(previous: UpdateInfo | None, new: UpdateInfo) -> UpdateInfo:
    """Keeps an already found update when a later check fails (e.g. offline)."""
    if new.error and previous is not None and previous.available:
        return UpdateInfo(True, previous.version, new.error)
    return new


def _trusted(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == ALLOWED_HOST or host.endswith("." + ALLOWED_HOST))


def is_git_checkout(app_dir: Path) -> bool:
    return (app_dir / ".git").exists()


def download(version: str, dest: Path, opener=urllib.request.urlopen) -> Path:
    """Downloads the release archive into dest; raises UpdateError on any problem."""
    path = dest / f"score-overlay-{version}.zip"
    try:
        with opener(ARCHIVE_URL.format(version=version), timeout=DOWNLOAD_TIMEOUT) as resp:
            final_url = resp.geturl()
            if not _trusted(final_url):
                raise UpdateError(t("err_redirect", url=final_url))
            path.write_bytes(resp.read())
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError(t("err_download", error=exc)) from exc
    if not zipfile.is_zipfile(path):
        raise UpdateError(t("err_not_zip"))
    return path


def _safe_members(z: zipfile.ZipFile) -> None:
    for name in z.namelist():
        parts = PurePosixPath(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or (parts and ":" in parts[0]):
            raise UpdateError(t("err_bad_path", name=name))


def _release_root(extracted: Path, expected_version: str) -> Path:
    starts = sorted(extracted.rglob("start.pyw"), key=lambda p: len(p.parts))
    if not starts:
        raise UpdateError(t("err_no_start"))
    root = starts[0].parent
    init = root / "overlay" / "__init__.py"
    if not init.is_file():
        raise UpdateError(t("err_no_init"))
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
    if not match or match.group(1) != expected_version:
        raise UpdateError(t("err_wrong_version", version=expected_version))
    return root


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy(child, dst / child.name)
    else:
        shutil.copy2(src, dst)


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _rollback(app_dir: Path, backup: Path, started: list[str], moved: list[str]) -> list[str]:
    """Best effort: removes partly copied entries and moves the old ones back.

    Returns the names that could not be restored.
    """
    problems = []
    for name in started:
        try:
            _remove(app_dir / name)
        except OSError:
            log.warning("rollback: cannot remove %s", name, exc_info=True)
            if name in moved:
                problems.append(name)
    for name in moved:
        if name in problems:
            continue
        try:
            (backup / name).rename(app_dir / name)
        except OSError:
            log.warning("rollback: cannot restore %s", name, exc_info=True)
            problems.append(name)
    return problems


def install(zip_path: Path, app_dir: Path, expected_version: str) -> None:
    """Replaces the program files in app_dir with the release in zip_path.

    Only names that are part of the release are replaced; anything else in app_dir (user files) is left
    alone. Replaced entries are moved to .update-backup/ and moved back if anything fails.
    """
    if is_git_checkout(app_dir):
        raise UpdateError(t("err_git"))
    if not _install_lock.acquire(blocking=False):
        raise UpdateError(t("err_running"))
    try:
        _install(zip_path, app_dir, expected_version)
    finally:
        _install_lock.release()


def _install(zip_path: Path, app_dir: Path, expected_version: str) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        extracted = Path(tmp)
        try:
            with zipfile.ZipFile(zip_path) as z:
                _safe_members(z)
                z.extractall(extracted)
        except zipfile.BadZipFile as exc:
            raise UpdateError(t("err_corrupt")) from exc
        root = _release_root(extracted, expected_version)
        names = sorted(p.name for p in root.iterdir() if p.name not in PRESERVED)

        backup = app_dir / BACKUP_DIR
        try:
            _remove(backup)
            backup.mkdir()
        except OSError as exc:
            raise UpdateError(t("err_backup", path=backup, error=exc)) from exc

        moved: list[str] = []
        started: list[str] = []
        try:
            for name in names:
                if (app_dir / name).exists():
                    (app_dir / name).rename(backup / name)
                    moved.append(name)
            for name in names:
                started.append(name)
                _copy(root / name, app_dir / name)
        except Exception as exc:
            problems = _rollback(app_dir, backup, started, moved)
            if problems:
                raise UpdateError(t("err_partial", error=exc, names=", ".join(problems), path=backup)) from exc
            raise UpdateError(t("err_rolled_back", error=exc)) from exc


def download_and_install(version: str, app_dir: Path, opener=urllib.request.urlopen) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        install(download(version, Path(tmp), opener=opener), app_dir, version)
