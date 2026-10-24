"""Self-update from Codeberg releases."""
import logging
from dataclasses import dataclass
from pathlib import Path

from overlay.sources.http import get_json
from overlay.version import is_newer, parse_version

RELEASE_URL = "https://codeberg.org/api/v1/repos/ElvonMF/score-overlay/releases/latest"
ARCHIVE_URL = "https://codeberg.org/ElvonMF/score-overlay/archive/v{version}.zip"

log = logging.getLogger(__name__)


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
