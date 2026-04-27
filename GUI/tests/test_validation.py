"""
Tests for input validation utilities.
"""

import pytest
from utils.validation import (
    validate_api_key,
    validate_url,
    validate_email,
    validate_company_name,
    validate_model_name,
)


def test_validate_api_key_anthropic():
    """Test Anthropic API key validation."""
    assert validate_api_key("sk-ant-" + "x" * 50, "anthropic")
    assert not validate_api_key("invalid", "anthropic")
    assert not validate_api_key("sk-ant-short", "anthropic")


def test_validate_api_key_openai():
    """Test OpenAI API key validation."""
    assert validate_api_key("sk-" + "x" * 40, "openai")
    assert not validate_api_key("invalid", "openai")


def test_validate_url():
    """Test URL validation."""
    assert validate_url("https://api.example.com")
    assert validate_url("https://localhost:8000", require_https=False)
    assert not validate_url("http://example.com", require_https=True)
    assert not validate_url("not-a-url")
    assert not validate_url("")


def test_validate_email():
    """Test email validation."""
    assert validate_email("user@example.com")
    assert validate_email("test.user+tag@domain.co.uk")
    assert not validate_email("invalid")
    assert not validate_email("@example.com")
    assert not validate_email("")


def test_validate_company_name():
    """Test company name validation."""
    assert validate_company_name("Google")
    assert validate_company_name("Meta Platforms, Inc.")
    assert validate_company_name("Acme & Co.")
    assert not validate_company_name("")
    assert not validate_company_name("A" * 300)  # Too long
    assert not validate_company_name("<script>alert('xss')</script>")


def test_validate_model_name():
    """Test model name validation."""
    assert validate_model_name("claude-opus-4-5", "anthropic")
    assert validate_model_name("gpt-4o", "openai")
    assert not validate_model_name("invalid-model", "anthropic")
    assert not validate_model_name("", "openai")
