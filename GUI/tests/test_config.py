"""
Tests for configuration management.
"""

import pytest
import tempfile
import os
from pathlib import Path
from settings.config import (
    load_config,
    save_config,
    get,
    set,
    DEFAULTS,
)


def test_load_default_config():
    """Test loading default config."""
    cfg = load_config()

    assert isinstance(cfg, dict)
    assert "selected_provider" in cfg
    assert cfg["selected_provider"] == "anthropic"


def test_save_and_load_config():
    """Test saving and loading config."""
    # Get current config
    cfg = load_config()

    # Modify a value
    original_opacity = cfg.get("opacity", 0.93)
    new_opacity = 0.85

    cfg["opacity"] = new_opacity
    save_config(cfg)

    # Reload and verify
    cfg2 = load_config()
    assert cfg2["opacity"] == new_opacity

    # Restore original
    cfg2["opacity"] = original_opacity
    save_config(cfg2)


def test_get_set_helpers():
    """Test get/set helper functions."""
    original_theme = get("theme", "dark")

    # Set new value
    set("theme", "light")

    # Verify
    assert get("theme") == "light"

    # Restore
    set("theme", original_theme)


def test_config_has_all_defaults():
    """Test that loaded config includes all default keys."""
    cfg = load_config()

    for key in DEFAULTS:
        assert key in cfg


def test_config_cache_invalidation():
    """Test that config cache invalidates on save."""
    from settings.config import invalidate_cache

    cfg1 = load_config()
    opacity1 = cfg1["opacity"]

    # Change and save
    cfg1["opacity"] = 0.77
    save_config(cfg1)

    # Load again (should get new value)
    cfg2 = load_config()
    assert cfg2["opacity"] == 0.77

    # Restore
    cfg2["opacity"] = opacity1
    save_config(cfg2)
