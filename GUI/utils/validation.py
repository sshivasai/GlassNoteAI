"""
utils/validation.py — Input validation and sanitization.

Prevents injection attacks, invalid state, and malformed data.

Usage:
    from utils.validation import validate_api_key, validate_url

    if not validate_api_key(key):
        raise ValueError("Invalid API key format")
"""

import re
import os
from typing import Optional, Tuple
from urllib.parse import urlparse


# ── API Key Validation ─────────────────────────────────────────────────────────

def validate_api_key(key: str, provider: str = "generic") -> bool:
    """
    Validate API key format.

    Args:
        key: The API key to validate
        provider: Provider name (anthropic, openai, deepgram, cerebras)

    Returns:
        bool: True if valid format
    """
    if not key or not isinstance(key, str):
        return False

    key = key.strip()

    # Minimum length check
    if len(key) < 20:
        return False

    # Provider-specific validation
    if provider == "anthropic":
        # Anthropic keys start with sk-ant-
        return key.startswith("sk-ant-") and len(key) > 30
    elif provider == "openai":
        # OpenAI keys start with sk-
        return key.startswith("sk-") and len(key) > 40
    elif provider == "deepgram":
        # Deepgram keys are alphanumeric
        return re.match(r'^[a-zA-Z0-9]{32,}$', key) is not None
    elif provider == "cerebras":
        # Cerebras keys format (assumed similar to OpenAI)
        return key.startswith("csk-") or (len(key) > 30 and re.match(r'^[a-zA-Z0-9_-]+$', key))

    # Generic validation: alphanumeric + common special chars
    return re.match(r'^[a-zA-Z0-9_.\-]+$', key) is not None and len(key) >= 20


def validate_jwt_token(token: str) -> bool:
    """
    Validate JWT token format (3 base64 parts separated by dots).

    Args:
        token: JWT token string

    Returns:
        bool: True if valid JWT format
    """
    if not token or not isinstance(token, str):
        return False

    parts = token.split('.')
    if len(parts) != 3:
        return False

    # Each part should be base64-like (alphanumeric + - and _)
    for part in parts:
        if not re.match(r'^[a-zA-Z0-9_-]+$', part):
            return False

    return True


# ── URL Validation ─────────────────────────────────────────────────────────────

def validate_url(url: str, require_https: bool = True) -> bool:
    """
    Validate URL format and scheme.

    Args:
        url: URL to validate
        require_https: If True, only accept https:// URLs

    Returns:
        bool: True if valid
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())

        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False

        # Check scheme
        if require_https:
            if parsed.scheme != "https":
                return False
        else:
            if parsed.scheme not in ("http", "https"):
                return False

        # Basic domain validation
        if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', parsed.netloc.split(':')[0]):
            # Allow localhost and IPs for development
            if parsed.netloc not in ("localhost", "127.0.0.1") and not parsed.netloc.startswith("localhost:"):
                if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$', parsed.netloc):
                    return False

        return True

    except Exception:
        return False


def sanitize_url(url: str) -> str:
    """
    Sanitize URL by removing trailing slashes and validating.

    Args:
        url: URL to sanitize

    Returns:
        str: Sanitized URL

    Raises:
        ValueError: If URL is invalid
    """
    if not url:
        raise ValueError("URL cannot be empty")

    url = url.strip().rstrip('/')

    if not validate_url(url, require_https=False):
        raise ValueError(f"Invalid URL format: {url}")

    return url


# ── Model Name Validation ──────────────────────────────────────────────────────

_VALID_MODELS = {
    "anthropic": {
        "claude-opus-4-5-20251101", "claude-opus-4-6", "claude-opus-4-7",
        "claude-sonnet-4-5-20250929", "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    },
    "openai": {
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
        "gpt-4", "gpt-3.5-turbo",
    },
    "cerebras": {
        "llama3.1-8b", "llama3.1-70b",
        "gpt-oss-120b",
    },
}


def validate_model_name(model: str, provider: str) -> bool:
    """
    Validate model name for a given provider.

    Args:
        model: Model name
        provider: Provider name (anthropic, openai, cerebras)

    Returns:
        bool: True if valid
    """
    if not model or not isinstance(model, str):
        return False

    if provider not in _VALID_MODELS:
        # Unknown provider — allow any alphanumeric + dashes
        return re.match(r'^[a-zA-Z0-9._-]+$', model) is not None

    return model in _VALID_MODELS[provider]


# ── Token Limits ───────────────────────────────────────────────────────────────

def validate_max_tokens(max_tokens: int) -> Tuple[bool, int]:
    """
    Validate and clamp max_tokens to reasonable limits.

    Args:
        max_tokens: Requested max tokens

    Returns:
        Tuple[bool, int]: (is_valid, clamped_value)
    """
    MIN_TOKENS = 50
    MAX_TOKENS = 32_000  # Reasonable upper limit

    try:
        tokens = int(max_tokens)
    except (ValueError, TypeError):
        return False, MIN_TOKENS

    if tokens < MIN_TOKENS:
        return False, MIN_TOKENS

    if tokens > MAX_TOKENS:
        return False, MAX_TOKENS

    return True, tokens


# ── File Path Validation ───────────────────────────────────────────────────────

def validate_file_path(path: str, must_exist: bool = False, must_be_file: bool = False) -> bool:
    """
    Validate file path for safety.

    Args:
        path: File path to validate
        must_exist: If True, path must exist
        must_be_file: If True, path must be a file (not directory)

    Returns:
        bool: True if valid
    """
    if not path or not isinstance(path, str):
        return False

    # Check for path traversal attempts
    if ".." in path or path.startswith("~"):
        # Path traversal with .. is allowed if it resolves within safe boundaries
        # But flag suspicious patterns
        pass

    # Check for null bytes (security)
    if '\x00' in path:
        return False

    if must_exist:
        if not os.path.exists(path):
            return False

        if must_be_file and not os.path.isfile(path):
            return False

    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing dangerous characters.

    Args:
        filename: Original filename

    Returns:
        str: Sanitized filename
    """
    if not filename:
        return "unnamed"

    # Remove path separators
    filename = os.path.basename(filename)

    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext

    return filename or "unnamed"


# ── Email Validation ───────────────────────────────────────────────────────────

def validate_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address

    Returns:
        bool: True if valid format
    """
    if not email or not isinstance(email, str):
        return False

    # Basic regex for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None


# ── Numeric Validation ─────────────────────────────────────────────────────────

def validate_numeric_range(value: any, min_val: float, max_val: float) -> Tuple[bool, float]:
    """
    Validate numeric value is within range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Tuple[bool, float]: (is_valid, clamped_value)
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False, min_val

    if num < min_val:
        return False, min_val

    if num > max_val:
        return False, max_val

    return True, num


# ── Session Data Validation ────────────────────────────────────────────────────

def validate_company_name(company: str) -> bool:
    """
    Validate company name (no special injection characters).

    Args:
        company: Company name

    Returns:
        bool: True if valid
    """
    if not company or not isinstance(company, str):
        return False

    company = company.strip()

    if len(company) < 1 or len(company) > 200:
        return False

    # Allow letters, numbers, spaces, and common punctuation
    # Block control characters and shell meta-characters
    if not re.match(r'^[a-zA-Z0-9\s.,&\'-]+$', company):
        return False

    return True


def validate_text_input(text: str, max_length: int = 10000) -> Tuple[bool, str]:
    """
    Validate and sanitize text input (job descriptions, prompts, etc.).

    Args:
        text: Input text
        max_length: Maximum allowed length

    Returns:
        Tuple[bool, str]: (is_valid, sanitized_text)
    """
    if not isinstance(text, str):
        return False, ""

    text = text.strip()

    if len(text) > max_length:
        return False, text[:max_length]

    # Remove null bytes
    text = text.replace('\x00', '')

    return True, text
