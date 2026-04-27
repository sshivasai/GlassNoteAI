"""
Pytest configuration for GUI tests.
"""

import pytest
import sys
import os

# Add GUI root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "selected_provider": "anthropic",
        "anthropic_model": "claude-opus-4-5",
        "max_tokens": 2048,
        "theme": "dark",
        "opacity": 0.93,
    }


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file."""
    config_dir = tmp_path / ".glassnote"
    config_dir.mkdir()
    config_file = config_dir / "config.json"

    yield config_file

    # Cleanup
    if config_file.exists():
        config_file.unlink()
