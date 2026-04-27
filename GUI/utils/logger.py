"""
utils/logger.py — Structured logging framework for GlassNote.

Replaces 200+ print() statements with proper logging.

Features:
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - File rotation (max 10MB per file, keep 5 backups)
  - Configurable verbosity
  - Thread-safe
  - Performance tracking decorator
  - Automatic PII redaction for API keys and tokens

Usage:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Session started")
    logger.error("API call failed", exc_info=True)
"""

import logging
import logging.handlers
import os
import re
import sys
import time
import functools
from pathlib import Path
from typing import Callable, Any

# ── Configuration ──────────────────────────────────────────────────────────────

LOG_DIR = Path.home() / ".glassnote" / "logs"
LOG_FILE = LOG_DIR / "glassnote.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# Default log level (can be overridden by config)
DEFAULT_LEVEL = logging.INFO

# Patterns to redact from logs (API keys, tokens, passwords)
_REDACT_PATTERNS = [
    (re.compile(r'(api[_-]?key["\s:=]+)["\']?([a-zA-Z0-9_-]{20,})["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(token["\s:=]+)["\']?([a-zA-Z0-9_.-]{20,})["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(password["\s:=]+)["\']?(.{8,})["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(Bearer\s+)([a-zA-Z0-9_.-]{20,})', re.IGNORECASE), r'\1***REDACTED***'),
]


def _redact_sensitive(message: str) -> str:
    """Remove API keys, tokens, and passwords from log messages."""
    for pattern, replacement in _REDACT_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class RedactingFormatter(logging.Formatter):
    """Formatter that automatically redacts sensitive information."""

    def format(self, record):
        original = super().format(record)
        return _redact_sensitive(original)


# ── Logger Setup ───────────────────────────────────────────────────────────────

_loggers_initialized = False
_root_logger = None


def setup_logging(level: int = DEFAULT_LEVEL, console: bool = True, file: bool = True) -> None:
    """
    Initialize the logging system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Enable console output
        file: Enable file output with rotation
    """
    global _loggers_initialized, _root_logger

    if _loggers_initialized:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get root logger
    _root_logger = logging.getLogger("glassnote")
    _root_logger.setLevel(level)
    _root_logger.handlers.clear()

    # Format: [2026-04-26 10:30:45] [INFO] [module.function] Message
    fmt = RedactingFormatter(
        fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (stdout)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(fmt)
        _root_logger.addHandler(console_handler)

    # File handler with rotation
    if file:
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                LOG_FILE,
                maxBytes=MAX_BYTES,
                backupCount=BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(fmt)
            _root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"[logger] Failed to create file handler: {e}")

    _loggers_initialized = True
    _root_logger.info("Logging system initialized")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        logging.Logger: Configured logger instance
    """
    if not _loggers_initialized:
        setup_logging()

    # Create child logger under glassnote namespace
    return logging.getLogger(f"glassnote.{name}")


def set_log_level(level: int) -> None:
    """
    Change the log level at runtime.

    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    if _root_logger:
        _root_logger.setLevel(level)
        for handler in _root_logger.handlers:
            handler.setLevel(level)


def log_performance(func: Callable) -> Callable:
    """
    Decorator to log function execution time.

    Usage:
        @log_performance
        def slow_function():
            time.sleep(1)
    """
    logger = get_logger(func.__module__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start) * 1000
            logger.debug(f"{func.__name__} completed in {elapsed_ms:.1f}ms")
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(
                f"{func.__name__} failed after {elapsed_ms:.1f}ms: {e}",
                exc_info=True
            )
            raise

    return wrapper


# ── Migration helpers ──────────────────────────────────────────────────────────

def migrate_print_to_logger():
    """
    Show migration examples for converting print() to logger calls.

    This is a documentation function — not meant to be called at runtime.
    """
    examples = """
    MIGRATION GUIDE: print() → logger

    Before:
        print("[app] Session started")
    After:
        logger.info("Session started")

    Before:
        print(f"[llm] Error: {e}")
    After:
        logger.error(f"LLM call failed: {e}", exc_info=True)

    Before:
        try:
            risky_operation()
        except Exception as e:
            print(f"[warn] Failed: {e}")
    After:
        try:
            risky_operation()
        except Exception as e:
            logger.warning(f"Operation failed (non-fatal): {e}", exc_info=True)

    Before:
        if DEBUG:
            print(f"[debug] Value: {x}")
    After:
        logger.debug(f"Value: {x}")
    """
    return examples


# Auto-initialize on import with defaults
setup_logging()
