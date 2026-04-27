"""
Tests for error handling utilities.
"""

import pytest
from utils.error_handler import (
    handle_error,
    ErrorContext,
    UserFriendlyError,
    handle_network_error,
    handle_api_key_error,
)


def test_user_friendly_error():
    """Test UserFriendlyError exception."""
    error = UserFriendlyError(
        user_message="Something went wrong",
        technical_detail="ValueError: invalid input"
    )

    assert error.user_message == "Something went wrong"
    assert error.technical_detail == "ValueError: invalid input"


def test_handle_error_basic():
    """Test basic error handling."""
    error = ValueError("test error")

    message = handle_error(
        error,
        context=ErrorContext.API_CALL,
        show_to_user=False
    )

    assert isinstance(message, str)
    assert len(message) > 0


def test_handle_network_error():
    """Test network error handling."""
    import httpx

    error = httpx.ConnectError("Connection refused")

    message = handle_network_error(error)

    assert "connect" in message.lower() or "connection" in message.lower()


def test_handle_api_key_error():
    """Test API key error handling."""
    message = handle_api_key_error("anthropic")

    assert "api key" in message.lower()
    assert "anthropic" in message.lower()


def test_error_context_types():
    """Test all error context types."""
    contexts = [
        ErrorContext.API_CALL,
        ErrorContext.FILE_IO,
        ErrorContext.NETWORK,
        ErrorContext.SCREENSHOT,
        ErrorContext.AUDIO,
        ErrorContext.LLM,
        ErrorContext.AUTH,
        ErrorContext.CONFIG,
        ErrorContext.UI,
        ErrorContext.DATABASE,
    ]

    for context in contexts:
        error = Exception("test")
        message = handle_error(error, context=context, show_to_user=False)
        assert isinstance(message, str)
        assert len(message) > 0
