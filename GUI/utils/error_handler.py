"""
utils/error_handler.py — Comprehensive error handling and user-friendly messages.

Provides:
  - User-friendly error messages (no stack traces shown to users)
  - Error recovery strategies
  - Graceful degradation
  - Error reporting to logs

Usage:
    from utils.error_handler import handle_error, ErrorContext

    try:
        risky_operation()
    except Exception as e:
        handle_error(e, context=ErrorContext.API_CALL, user_message="Failed to connect")
"""

import traceback
from enum import Enum
from typing import Optional, Callable
from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorContext(Enum):
    """Error context for categorizing failures."""
    API_CALL = "api_call"
    FILE_IO = "file_io"
    NETWORK = "network"
    SCREENSHOT = "screenshot"
    AUDIO = "audio"
    LLM = "llm"
    AUTH = "auth"
    CONFIG = "config"
    UI = "ui"
    DATABASE = "database"
    UNKNOWN = "unknown"


class UserFriendlyError(Exception):
    """Exception with user-friendly message."""

    def __init__(self, user_message: str, technical_detail: str = ""):
        self.user_message = user_message
        self.technical_detail = technical_detail
        super().__init__(user_message)


# ── Error Message Mapping ──────────────────────────────────────────────────────

_ERROR_MESSAGES = {
    # Network errors
    "ConnectionError": "Cannot connect to the server. Please check your internet connection.",
    "TimeoutError": "Connection timed out. Please try again.",
    "ConnectTimeout": "Failed to connect to the server. Please check your network.",
    "ReadTimeout": "Server took too long to respond. Please try again.",

    # API errors
    "401": "Authentication failed. Please check your API key in Settings.",
    "402": "Quota exceeded. Please upgrade your plan or add credits.",
    "403": "Access denied. Please check your permissions.",
    "404": "Resource not found. The requested endpoint may have changed.",
    "429": "Rate limit exceeded. Please wait a moment and try again.",
    "500": "Server error. Please try again later.",
    "503": "Service unavailable. Please try again later.",

    # File errors
    "FileNotFoundError": "File not found. Please check the file path.",
    "PermissionError": "Permission denied. Please check file permissions.",
    "IsADirectoryError": "Expected a file but got a directory.",

    # Audio errors
    "NoAudioDevice": "No audio device found. Please check your audio settings.",
    "AudioInitFailed": "Failed to initialize audio. Please restart the application.",

    # Screenshot errors
    "ScreenshotFailed": "Failed to capture screenshot. Please try again.",
    "DisplayNotFound": "Display not found. Please check your monitor connections.",

    # LLM errors
    "InvalidModel": "Invalid model name. Please check your settings.",
    "PromptTooLong": "Your input is too long. Please try with shorter text.",
    "ContentFiltered": "Content was filtered by the AI provider. Please rephrase your input.",

    # Config errors
    "ConfigCorrupted": "Configuration file is corrupted. Resetting to defaults.",
}


def _get_user_friendly_message(error: Exception, context: ErrorContext) -> str:
    """
    Convert technical error to user-friendly message.

    Args:
        error: The exception that occurred
        context: Error context for better messaging

    Returns:
        str: User-friendly error message
    """
    error_type = type(error).__name__
    error_str = str(error).lower()

    # Check predefined messages
    if error_type in _ERROR_MESSAGES:
        return _ERROR_MESSAGES[error_type]

    # Check HTTP status codes
    for code, message in _ERROR_MESSAGES.items():
        if code.isdigit() and code in error_str:
            return message

    # Context-specific generic messages
    context_messages = {
        ErrorContext.API_CALL: "API request failed. Please check your connection and try again.",
        ErrorContext.NETWORK: "Network error occurred. Please check your internet connection.",
        ErrorContext.FILE_IO: "File operation failed. Please check file permissions.",
        ErrorContext.SCREENSHOT: "Screenshot capture failed. Please try again.",
        ErrorContext.AUDIO: "Audio operation failed. Please check your audio device.",
        ErrorContext.LLM: "AI model request failed. Please try again.",
        ErrorContext.AUTH: "Authentication failed. Please check your credentials.",
        ErrorContext.CONFIG: "Configuration error. Please check your settings.",
        ErrorContext.UI: "UI operation failed. Please restart the application if this persists.",
        ErrorContext.DATABASE: "Database error occurred. Please try again.",
    }

    return context_messages.get(context, "An error occurred. Please try again.")


# ── Error Handler ──────────────────────────────────────────────────────────────

def handle_error(
    error: Exception,
    context: ErrorContext = ErrorContext.UNKNOWN,
    user_message: Optional[str] = None,
    show_to_user: bool = True,
    on_error_callback: Optional[Callable[[str], None]] = None,
    critical: bool = False,
) -> str:
    """
    Handle an error with logging and optional user notification.

    Args:
        error: The exception that occurred
        context: Error context category
        user_message: Optional custom user-friendly message
        show_to_user: Whether to show error to user
        on_error_callback: Optional callback to display error (e.g., overlay.set_error)
        critical: If True, log as critical and may require app restart

    Returns:
        str: User-friendly error message
    """
    # Get technical details
    technical_detail = f"{type(error).__name__}: {str(error)}"
    stack_trace = traceback.format_exc()

    # Log the error with full details
    if critical:
        logger.critical(
            f"Critical error in {context.value}: {technical_detail}\n{stack_trace}"
        )
    else:
        logger.error(
            f"Error in {context.value}: {technical_detail}",
            exc_info=True
        )

    # Get user-friendly message
    if user_message:
        friendly_message = user_message
    else:
        friendly_message = _get_user_friendly_message(error, context)

    # Show to user if requested
    if show_to_user and on_error_callback:
        on_error_callback(friendly_message)

    return friendly_message


# ── Specific Error Handlers ────────────────────────────────────────────────────

def handle_network_error(error: Exception, on_error: Optional[Callable] = None) -> str:
    """Handle network-related errors."""
    import httpx

    if isinstance(error, httpx.ConnectError):
        msg = "Cannot connect to the server. Please check:\n• Internet connection\n• Firewall settings\n• API URL"
    elif isinstance(error, httpx.TimeoutException):
        msg = "Connection timed out. The server may be slow or unreachable."
    elif isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        msg = _ERROR_MESSAGES.get(str(status), f"Server returned error {status}")
    else:
        msg = "Network error occurred. Please check your internet connection."

    return handle_error(error, ErrorContext.NETWORK, msg, on_error_callback=on_error)


def handle_file_error(error: Exception, file_path: str = "", on_error: Optional[Callable] = None) -> str:
    """Handle file I/O errors."""
    if isinstance(error, FileNotFoundError):
        msg = f"File not found: {file_path}" if file_path else "File not found"
    elif isinstance(error, PermissionError):
        msg = f"Permission denied accessing: {file_path}" if file_path else "Permission denied"
    elif isinstance(error, IsADirectoryError):
        msg = f"Expected a file but got a directory: {file_path}"
    else:
        msg = f"File operation failed: {file_path}" if file_path else "File operation failed"

    return handle_error(error, ErrorContext.FILE_IO, msg, on_error_callback=on_error)


def handle_api_key_error(provider: str, on_error: Optional[Callable] = None) -> str:
    """Handle missing or invalid API key."""
    msg = (
        f"No {provider.title()} API key configured.\n\n"
        f"Please add your API key in Settings → API Keys"
    )

    error = UserFriendlyError(msg, f"Missing {provider} API key")
    return handle_error(error, ErrorContext.AUTH, msg, on_error_callback=on_error)


def handle_quota_exceeded(plan: str, on_error: Optional[Callable] = None) -> str:
    """Handle quota/rate limit exceeded."""
    msg = (
        f"Your {plan} plan quota has been exceeded.\n\n"
        "Please:\n"
        "• Wait for your quota to reset\n"
        "• Upgrade your plan\n"
        "• Add more credits"
    )

    error = UserFriendlyError(msg, "Quota exceeded")
    return handle_error(error, ErrorContext.API_CALL, msg, on_error_callback=on_error)


# ── Recovery Strategies ────────────────────────────────────────────────────────

def with_retry(
    func: Callable,
    max_attempts: int = 3,
    backoff_factor: float = 1.5,
    on_error: Optional[Callable] = None,
):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_attempts: Maximum retry attempts
        backoff_factor: Backoff multiplier between attempts
        on_error: Callback for errors

    Returns:
        Function result or raises last exception
    """
    import time

    last_error = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")

            if attempt < max_attempts - 1:
                sleep_time = backoff_factor ** attempt
                logger.info(f"Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            else:
                # Last attempt failed
                if on_error:
                    handle_error(e, on_error_callback=on_error)
                raise

    # Should never reach here, but just in case
    if last_error:
        raise last_error


# ── Context Manager for Error Handling ─────────────────────────────────────────

class ErrorBoundary:
    """
    Context manager for automatic error handling.

    Usage:
        with ErrorBoundary(context=ErrorContext.API_CALL, on_error=overlay.set_error):
            risky_operation()
    """

    def __init__(
        self,
        context: ErrorContext = ErrorContext.UNKNOWN,
        user_message: Optional[str] = None,
        on_error: Optional[Callable] = None,
        suppress: bool = False,
    ):
        self.context = context
        self.user_message = user_message
        self.on_error = on_error
        self.suppress = suppress

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            handle_error(
                exc_val,
                context=self.context,
                user_message=self.user_message,
                on_error_callback=self.on_error,
            )
            return self.suppress  # Suppress exception if requested
        return False
