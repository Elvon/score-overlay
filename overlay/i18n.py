# SPDX-License-Identifier: GPL-3.0-or-later
"""User interface texts in German and English; another language is another dictionary."""
import ctypes
from datetime import datetime
from typing import Callable

LANGUAGES = ("de", "en")
DEFAULT = "en"
GERMAN = 0x07  # primary language id, all German variants

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "menu_refresh": "Aktualisieren",
        "menu_preview": "Vorschau",
        "menu_all_bl": "Alle Bundesliga-Spiele",
        "menu_all_ucl": "Alle Champions-League-Spiele",
        "menu_sound": "Ton bei Tor",
        "menu_language": "Sprache / Language",
        "menu_about": "Über Score-Overlay…",
        "menu_quit": "Beenden",
        "update_install": "Update auf v{version} installieren",
        "update_installing": "Update auf v{version} wird installiert…",
        "update_git": "v{version} verfügbar – per git pull aktualisieren",
        "update_question": "Version {version} herunterladen und installieren?\nDas Overlay startet danach neu.",
        "update_failed_title": "Update fehlgeschlagen",
        "status_unchecked": "Noch nicht geprüft",
        "status_available": "v{version} verfügbar",
        "status_last_failed": " (letzte Prüfung fehlgeschlagen)",
        "status_failed": "Prüfung fehlgeschlagen",
        "status_current": "Aktuell",
        "status_checking": "Wird geprüft…",
        "about_title": "Über Score-Overlay",
        "about_version": "Version {version}",
        "about_license": "Lizenz: {license}",
        "about_warranty": "Ohne jede Gewährleistung – siehe LICENSE",
        "about_data": "Daten: OpenLigaDB, ESPN, TheSportsDB, optional goal-api.com",
        "about_update": "Update: {status}",
        "about_check": "Nach Updates suchen",
        "about_close": "Schließen",
        "goal_penalty": " (Elfm.)",
        "goal_own": " (ET)",
        "tooltip_click": "Klick: Google-Suche",
        "finished": "Ende",
        "half_time": "HZ",
        "err_redirect": "Download wurde auf eine unerwartete Adresse umgeleitet: {url}",
        "err_download": "Download fehlgeschlagen: {error}",
        "err_not_zip": "Download ist kein ZIP-Archiv",
        "err_bad_path": "Unzulässiger Pfad im Archiv: {name}",
        "err_no_start": "Archiv enthält kein start.pyw",
        "err_no_init": "Archiv enthält kein overlay/__init__.py",
        "err_wrong_version": "Archiv enthält nicht Version {version}",
        "err_git": "Git-Ordner: bitte per git pull aktualisieren",
        "err_running": "Ein Update läuft bereits",
        "err_corrupt": "Archiv ist beschädigt",
        "err_backup": "Kann {path} nicht anlegen (Schreibrechte? Ordner löschen?): {error}",
        "err_partial": "Installation fehlgeschlagen ({error}). Nicht wiederhergestellt: {names}. "
                       "Der alte Stand liegt in {path} - bitte von dort zurückkopieren.",
        "err_rolled_back": "Installation fehlgeschlagen, alter Stand wiederhergestellt: {error}",
    },
    "en": {
        "menu_refresh": "Refresh",
        "menu_preview": "Preview",
        "menu_all_bl": "All Bundesliga matches",
        "menu_all_ucl": "All Champions League matches",
        "menu_sound": "Sound on goal",
        "menu_language": "Sprache / Language",
        "menu_about": "About Score-Overlay…",
        "menu_quit": "Quit",
        "update_install": "Install update to v{version}",
        "update_installing": "Installing update to v{version}…",
        "update_git": "v{version} available – update with git pull",
        "update_question": "Download and install version {version}?\nThe overlay will restart afterwards.",
        "update_failed_title": "Update failed",
        "status_unchecked": "Not checked yet",
        "status_available": "v{version} available",
        "status_last_failed": " (last check failed)",
        "status_failed": "Check failed",
        "status_current": "Up to date",
        "status_checking": "Checking…",
        "about_title": "About Score-Overlay",
        "about_version": "Version {version}",
        "about_license": "License: {license}",
        "about_warranty": "No warranty – see LICENSE",
        "about_data": "Data: OpenLigaDB, ESPN, TheSportsDB, optionally goal-api.com",
        "about_update": "Update: {status}",
        "about_check": "Check for updates",
        "about_close": "Close",
        "goal_penalty": " (pen.)",
        "goal_own": " (o.g.)",
        "tooltip_click": "Click: Google search",
        "finished": "FT",
        "half_time": "HT",
        "err_redirect": "Download was redirected to an unexpected address: {url}",
        "err_download": "Download failed: {error}",
        "err_not_zip": "Download is not a ZIP archive",
        "err_bad_path": "Invalid path in archive: {name}",
        "err_no_start": "Archive contains no start.pyw",
        "err_no_init": "Archive contains no overlay/__init__.py",
        "err_wrong_version": "Archive does not contain version {version}",
        "err_git": "Git folder: please update with git pull",
        "err_running": "An update is already running",
        "err_corrupt": "Archive is corrupt",
        "err_backup": "Cannot create {path} (write permission? delete the folder?): {error}",
        "err_partial": "Installation failed ({error}). Not restored: {names}. "
                       "The previous version is in {path} - please copy it back from there.",
        "err_rolled_back": "Installation failed, previous version restored: {error}",
    },
}
WEEKDAYS = {
    "de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_current = DEFAULT


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else DEFAULT


def language() -> str:
    return _current


def t(key: str, **values) -> str:
    return STRINGS[_current][key].format(**values)


def short_date(dt: datetime) -> str:
    """Weekday and date of a local datetime, e.g. "Sa 31.10." / "Sat 31 Oct"."""
    weekday = WEEKDAYS[_current][dt.weekday()]
    if _current == "de":
        return f"{weekday} {dt:%d.%m.}"
    return f"{weekday} {dt.day} {MONTHS_EN[dt.month - 1]}"


def _windows_langid() -> int:
    return ctypes.windll.kernel32.GetUserDefaultUILanguage()


def system_language(get_langid: Callable[[], int] | None = None) -> str:
    """"de" for a German Windows display language, otherwise "en"."""
    try:
        langid = (get_langid or _windows_langid)()
    except Exception:
        return DEFAULT
    return "de" if langid & 0x3FF == GERMAN else DEFAULT


def resolve(configured: object, get_langid: Callable[[], int] | None = None) -> str:
    """The language from config.json if valid, otherwise the Windows display language."""
    return configured if configured in LANGUAGES else system_language(get_langid)
