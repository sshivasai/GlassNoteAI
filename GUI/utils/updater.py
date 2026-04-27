"""
utils/updater.py — Auto-update functionality for GlassNote.

Checks for new versions from the backend and prompts user to update.

Usage:
    from utils.updater import check_for_updates

    check_for_updates(
        current_version="1.0.0",
        api_url="https://api.glassnote.ai",
        on_update_available=show_update_dialog
    )
"""

import re
import threading
from typing import Callable, Optional, Tuple
from packaging import version as pkg_version
from utils.logger import get_logger

logger = get_logger(__name__)

# Current app version (should be updated with each release)
APP_VERSION = "1.0.0"


def parse_version(version_str: str) -> Optional[pkg_version.Version]:
    """
    Parse semantic version string.

    Args:
        version_str: Version string (e.g., "1.2.3")

    Returns:
        Optional[Version]: Parsed version or None if invalid
    """
    try:
        return pkg_version.parse(version_str)
    except Exception as e:
        logger.warning(f"Invalid version string: {version_str} ({e})")
        return None


def compare_versions(current: str, latest: str) -> Tuple[bool, str]:
    """
    Compare version strings.

    Args:
        current: Current version
        latest: Latest available version

    Returns:
        Tuple[bool, str]: (is_newer, comparison_detail)
    """
    current_ver = parse_version(current)
    latest_ver = parse_version(latest)

    if current_ver is None or latest_ver is None:
        return False, "Invalid version format"

    if latest_ver > current_ver:
        return True, f"Update available: {current} → {latest}"
    elif latest_ver == current_ver:
        return False, "You're on the latest version"
    else:
        return False, f"You're ahead: {current} > {latest}"


def check_for_updates(
    current_version: str = APP_VERSION,
    api_url: str = "",
    on_update_available: Optional[Callable[[dict], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
    silent: bool = False,
) -> None:
    """
    Check for application updates from the backend.

    Args:
        current_version: Current app version
        api_url: GlassNote API URL
        on_update_available: Callback with update info dict
        on_error: Callback for errors
        silent: If True, only call callback if update is available
    """
    if not api_url:
        from settings import config
        api_url = config.get("glassnote_api_url", "")

    if not api_url:
        logger.debug("No API URL configured, skipping update check")
        return

    def _check():
        try:
            import httpx

            logger.info(f"Checking for updates (current: {current_version})...")

            with httpx.Client(
                http2=True,
                timeout=httpx.Timeout(10.0, connect=5.0),
            ) as client:
                r = client.get(
                    f"{api_url}/api/public/version",
                    params={"platform": "windows"},
                )

            if r.status_code != 200:
                error_msg = f"Update check failed (HTTP {r.status_code})"
                logger.warning(error_msg)
                if on_error and not silent:
                    on_error(error_msg)
                return

            data = r.json()

            latest_version = data.get("version", "")
            download_url = data.get("download_url", "")
            release_notes = data.get("release_notes", "")
            is_critical = data.get("is_critical", False)

            if not latest_version:
                logger.warning("Server returned empty version")
                return

            # Compare versions
            is_newer, detail = compare_versions(current_version, latest_version)

            logger.info(detail)

            if is_newer and on_update_available:
                update_info = {
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "download_url": download_url,
                    "release_notes": release_notes,
                    "is_critical": is_critical,
                }
                on_update_available(update_info)
            elif not is_newer and not silent:
                logger.info("Already on latest version")

        except Exception as e:
            error_msg = f"Update check error: {e}"
            logger.error(error_msg, exc_info=True)
            if on_error and not silent:
                on_error(error_msg)

    # Run in background thread
    threading.Thread(
        target=_check,
        daemon=True,
        name="update-check"
    ).start()


def get_current_version() -> str:
    """
    Get current application version.

    Reads from version_info.txt if available, otherwise returns APP_VERSION.

    Returns:
        str: Current version string
    """
    import os

    # Try to read from version_info.txt (created by build.py)
    try:
        version_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "version_info.txt"
        )

        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("FileVersion"):
                        # Extract version from "FileVersion=1.0.0.0"
                        match = re.search(r'FileVersion=([0-9.]+)', line)
                        if match:
                            ver = match.group(1)
                            # Convert "1.0.0.0" to "1.0.0"
                            parts = ver.split('.')[:3]
                            return '.'.join(parts)
    except Exception as e:
        logger.debug(f"Could not read version file: {e}")

    return APP_VERSION


def format_release_notes(notes: str, max_lines: int = 10) -> str:
    """
    Format release notes for display.

    Args:
        notes: Raw release notes (markdown or plain text)
        max_lines: Maximum lines to show

    Returns:
        str: Formatted notes
    """
    if not notes:
        return "No release notes available."

    lines = notes.split('\n')

    # Truncate if too long
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines.append("...")

    return '\n'.join(lines)


def open_download_url(url: str) -> bool:
    """
    Open download URL in user's default browser.

    Args:
        url: Download URL

    Returns:
        bool: True if opened successfully
    """
    if not url:
        return False

    try:
        import webbrowser
        webbrowser.open(url)
        logger.info(f"Opened download URL: {url}")
        return True
    except Exception as e:
        logger.error(f"Failed to open URL: {e}", exc_info=True)
        return False


# ── Update Notification Dialog Helper ─────────────────────────────────────────

def show_update_notification(update_info: dict, tray_manager=None):
    """
    Show system tray notification for available update.

    Args:
        update_info: Update information dict
        tray_manager: Optional TrayManager instance for notifications
    """
    latest = update_info.get("latest_version", "")
    is_critical = update_info.get("is_critical", False)

    title = "Critical Update Available!" if is_critical else "Update Available"
    message = f"GlassNote {latest} is now available.\nClick to download."

    if tray_manager:
        tray_manager.show_notification(title, message, duration_ms=10000)
    else:
        logger.info(f"{title}: {message}")
