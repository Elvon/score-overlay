"""Self-update from Codeberg releases."""
import logging
import re
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from overlay.sources.http import get_json
from overlay.version import is_newer, parse_version

RELEASE_URL = "https://codeberg.org/api/v1/repos/ElvonMF/score-overlay/releases/latest"
ARCHIVE_URL = "https://codeberg.org/ElvonMF/score-overlay/archive/v{version}.zip"

# Never touched by an update.
PRESERVED = {"config.json", "overlay.log", ".update-backup", ".git"}
BACKUP_DIR = ".update-backup"
DOWNLOAD_TIMEOUT = 30

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


def is_git_checkout(app_dir: Path) -> bool:
    return (app_dir / ".git").exists()


def download(version: str, dest: Path, opener=urllib.request.urlopen) -> Path:
    """Downloads the release archive into dest; raises UpdateError on any problem."""
    path = dest / f"score-overlay-{version}.zip"
    try:
        with opener(ARCHIVE_URL.format(version=version), timeout=DOWNLOAD_TIMEOUT) as resp:
            path.write_bytes(resp.read())
    except Exception as exc:
        raise UpdateError(f"Download fehlgeschlagen: {exc}") from exc
    if not zipfile.is_zipfile(path):
        raise UpdateError("Download ist kein ZIP-Archiv")
    return path


def _safe_members(z: zipfile.ZipFile) -> None:
    for name in z.namelist():
        parts = PurePosixPath(name).parts
        if name.startswith(("/", "\\")) or ".." in parts or (parts and ":" in parts[0]):
            raise UpdateError(f"Unzulässiger Pfad im Archiv: {name}")


def _release_root(extracted: Path, expected_version: str) -> Path:
    starts = sorted(extracted.rglob("start.pyw"), key=lambda p: len(p.parts))
    if not starts:
        raise UpdateError("Archiv enthält kein start.pyw")
    root = starts[0].parent
    init = root / "overlay" / "__init__.py"
    if not init.is_file():
        raise UpdateError("Archiv enthält kein overlay/__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
    if not match or match.group(1) != expected_version:
        raise UpdateError(f"Archiv enthält nicht Version {expected_version}")
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


def install(zip_path: Path, app_dir: Path, expected_version: str) -> None:
    """Replaces the program files in app_dir with the release in zip_path.

    Old files are moved to .update-backup/ and moved back if anything fails.
    """
    if is_git_checkout(app_dir):
        raise UpdateError("Git-Ordner: bitte per git pull aktualisieren")
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp)
        try:
            with zipfile.ZipFile(zip_path) as z:
                _safe_members(z)
                z.extractall(extracted)
        except zipfile.BadZipFile as exc:
            raise UpdateError("Archiv ist beschädigt") from exc
        root = _release_root(extracted, expected_version)

        backup = app_dir / BACKUP_DIR
        _remove(backup)
        backup.mkdir()
        old = [p for p in app_dir.iterdir() if p.name not in PRESERVED]
        for p in old:
            p.rename(backup / p.name)
        try:
            for src in root.iterdir():
                if src.name not in PRESERVED:
                    _copy(src, app_dir / src.name)
        except Exception as exc:
            for p in app_dir.iterdir():
                if p.name not in PRESERVED:
                    _remove(p)
            for p in backup.iterdir():
                p.rename(app_dir / p.name)
            raise UpdateError(f"Installation fehlgeschlagen, alter Stand wiederhergestellt: {exc}") from exc
