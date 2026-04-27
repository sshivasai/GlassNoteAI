"""
utils/telemetry.py — Telemetry and crash reporting (opt-in).

Integrates with Sentry or similar for error tracking.

Usage:
    from utils.telemetry import init_telemetry, capture_exception

    init_telemetry(dsn="https://...", opt_in=True)

    try:
        risky_operation()
    except Exception as e:
        capture_exception(e)
"""

import os
import sys
from typing import Optional, Dict, Any
from settings import config
from utils.logger import get_logger

logger = get_logger(__name__)

# Sentry SDK (optional dependency)
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    SENTRY_AVAILABLE = False


_TELEMETRY_ENABLED = False
_USER_OPT_IN = False


def is_telemetry_available() -> bool:
    """Check if telemetry dependencies are installed."""
    return SENTRY_AVAILABLE


def is_telemetry_enabled() -> bool:
    """Check if telemetry is currently enabled."""
    return _TELEMETRY_ENABLED and _USER_OPT_IN


def init_telemetry(
    dsn: Optional[str] = None,
    environment: str = "production",
    release: Optional[str] = None,
) -> bool:
    """
    Initialize telemetry system.

    Args:
        dsn: Sentry DSN (if None, reads from config)
        environment: Environment name
        release: Release version

    Returns:
        bool: True if initialized successfully
    """
    global _TELEMETRY_ENABLED, _USER_OPT_IN

    # Check user opt-in
    cfg = config.load_config()
    _USER_OPT_IN = cfg.get("telemetry_opt_in", False)

    if not _USER_OPT_IN:
        logger.info("Telemetry disabled: user has not opted in")
        return False

    if not SENTRY_AVAILABLE:
        logger.warning("Telemetry disabled: sentry-sdk not installed (pip install sentry-sdk)")
        return False

    # Get DSN
    if dsn is None:
        dsn = cfg.get("sentry_dsn", "")

    if not dsn:
        logger.warning("Telemetry disabled: no Sentry DSN configured")
        return False

    # Get release version
    if release is None:
        from utils.updater import get_current_version
        release = f"glassnote@{get_current_version()}"

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0.1,  # 10% performance monitoring
            profiles_sample_rate=0.1,  # 10% profiling
            send_default_pii=False,  # Don't send PII
            before_send=_before_send_filter,
        )

        _TELEMETRY_ENABLED = True
        logger.info(f"Telemetry initialized: {environment} / {release}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}", exc_info=True)
        return False


def _before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter telemetry events before sending.

    Removes sensitive data and applies privacy rules.

    Args:
        event: Sentry event dict
        hint: Hint dict with exception info

    Returns:
        Optional[Dict]: Filtered event or None to drop
    """
    # Remove API keys from breadcrumbs and context
    if 'breadcrumbs' in event:
        for crumb in event['breadcrumbs'].get('values', []):
            if 'data' in crumb:
                for key in list(crumb['data'].keys()):
                    if 'key' in key.lower() or 'token' in key.lower():
                        crumb['data'][key] = '[REDACTED]'

    # Remove sensitive context
    if 'contexts' in event:
        for context_name, context_data in event['contexts'].items():
            if isinstance(context_data, dict):
                for key in list(context_data.keys()):
                    if 'key' in key.lower() or 'token' in key.lower() or 'password' in key.lower():
                        context_data[key] = '[REDACTED]'

    return event


def capture_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> None:
    """
    Capture an exception for telemetry.

    Args:
        exception: Exception to capture
        context: Additional context data
        level: Severity level (debug, info, warning, error, fatal)
    """
    if not is_telemetry_enabled():
        return

    try:
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                scope.level = level
                sentry_sdk.capture_exception(exception)
        else:
            sentry_sdk.capture_exception(exception)

        logger.debug(f"Exception captured for telemetry: {type(exception).__name__}")

    except Exception as e:
        logger.error(f"Failed to capture exception: {e}", exc_info=True)


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Capture a message for telemetry.

    Args:
        message: Message to capture
        level: Severity level
        context: Additional context
    """
    if not is_telemetry_enabled():
        return

    try:
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                scope.level = level
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)

    except Exception as e:
        logger.error(f"Failed to capture message: {e}", exc_info=True)


def set_user_context(user_id: str, email: Optional[str] = None, plan: Optional[str] = None):
    """
    Set user context for telemetry.

    Args:
        user_id: User ID (hashed/anonymized)
        email: User email (optional)
        plan: User plan (optional)
    """
    if not is_telemetry_enabled():
        return

    try:
        user_data = {"id": user_id}
        if email:
            user_data["email"] = email
        if plan:
            user_data["plan"] = plan

        sentry_sdk.set_user(user_data)

    except Exception as e:
        logger.error(f"Failed to set user context: {e}", exc_info=True)


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
):
    """
    Add a breadcrumb for debugging context.

    Args:
        message: Breadcrumb message
        category: Category (navigation, http, etc.)
        level: Severity level
        data: Additional data
    """
    if not is_telemetry_enabled():
        return

    try:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )
    except Exception as e:
        logger.error(f"Failed to add breadcrumb: {e}", exc_info=True)


def flush_telemetry(timeout: float = 2.0):
    """
    Flush telemetry events.

    Args:
        timeout: Maximum time to wait in seconds
    """
    if not is_telemetry_enabled():
        return

    try:
        sentry_sdk.flush(timeout=timeout)
    except Exception as e:
        logger.error(f"Failed to flush telemetry: {e}", exc_info=True)


# ── Opt-in Management ──────────────────────────────────────────────────────────

def show_telemetry_consent_dialog(parent=None) -> bool:
    """
    Show telemetry opt-in dialog.

    Args:
        parent: Parent widget

    Returns:
        bool: True if user opted in
    """
    from PyQt6.QtWidgets import QMessageBox

    msg = QMessageBox(parent)
    msg.setWindowTitle("Help Improve GlassNote")
    msg.setText(
        "<b>Help us improve GlassNote</b>\n\n"
        "Would you like to send anonymous crash reports and usage data?\n\n"
        "This helps us fix bugs and improve the app. "
        "No personal data or API keys are ever sent."
    )
    msg.setInformativeText(
        "You can change this later in Settings → Privacy."
    )
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.No)

    result = msg.exec()

    opted_in = (result == QMessageBox.StandardButton.Yes)

    # Save preference
    cfg = config.load_config()
    cfg["telemetry_opt_in"] = opted_in
    config.save_config(cfg)

    return opted_in


def set_telemetry_opt_in(opt_in: bool):
    """
    Set telemetry opt-in preference.

    Args:
        opt_in: True to enable telemetry
    """
    cfg = config.load_config()
    cfg["telemetry_opt_in"] = opt_in
    config.save_config(cfg)

    logger.info(f"Telemetry opt-in: {opt_in}")
