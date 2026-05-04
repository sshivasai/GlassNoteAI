"""
utils/keybind_config.py — Keyboard shortcut configuration.

Manages customizable keyboard shortcuts with conflict detection.

Usage:
    from utils.keybind_config import keybind_manager

    # Get shortcut
    shortcut = keybind_manager.get_shortcut("capture")

    # Set shortcut
    success = keybind_manager.set_shortcut("capture", "Ctrl+Alt+C")

    # Check for conflicts
    conflicts = keybind_manager.check_conflicts("Ctrl+Shift+C")
"""

from typing import Dict, Optional, List, Tuple
from settings import config
from utils.logger import get_logger

logger = get_logger(__name__)


# Default keyboard shortcuts
DEFAULT_SHORTCUTS = {
    "capture": "Ctrl+Shift+C",
    "solve": "Ctrl+Shift+S",
    "analyze": "Ctrl+Shift+A",
    "debug": "Ctrl+Shift+D",
    "interview": "Ctrl+Shift+I",
    "toggle_overlay": "Ctrl+Shift+H",
    "end_session": "Ctrl+Shift+Q",
    "prev_history": "Ctrl+Shift+[",
    "next_history": "Ctrl+Shift+]",
    "move_up": "Ctrl+Shift+Up",
    "move_down": "Ctrl+Shift+Down",
    "move_left": "Ctrl+Shift+Left",
    "move_right": "Ctrl+Shift+Right",
}


# Action descriptions for UI
ACTION_DESCRIPTIONS = {
    "capture": "Capture Screenshot",
    "solve": "Solve Queued Screenshots",
    "analyze": "Instant Capture + Analyze",
    "debug": "Debug/Review Code (Screenshot)",
    "interview": "Start/Stop Interview Mode",
    "toggle_overlay": "Show/Hide Answer Overlay",
    "end_session": "End Current Session",
    "prev_history": "Previous Answer",
    "next_history": "Next Answer",
    "move_up": "Move Overlay Up",
    "move_down": "Move Overlay Down",
    "move_left": "Move Overlay Left",
    "move_right": "Move Overlay Right",
}


class KeybindManager:
    """Manage keyboard shortcut configuration."""

    def __init__(self):
        self._shortcuts: Dict[str, str] = {}
        self._load_shortcuts()

    def _load_shortcuts(self):
        """Load shortcuts from config."""
        cfg = config.load_config()
        saved = cfg.get("keyboard_shortcuts", {})

        # Start with defaults
        self._shortcuts = DEFAULT_SHORTCUTS.copy()

        # Override with saved values
        self._shortcuts.update(saved)

    def _save_shortcuts(self):
        """Save shortcuts to config."""
        cfg = config.load_config()
        cfg["keyboard_shortcuts"] = self._shortcuts
        config.save_config(cfg)

    def get_shortcut(self, action: str) -> str:
        """
        Get keyboard shortcut for action.

        Args:
            action: Action name

        Returns:
            str: Shortcut string (e.g., "Ctrl+Shift+C")
        """
        return self._shortcuts.get(action, "")

    def set_shortcut(self, action: str, shortcut: str) -> Tuple[bool, str]:
        """
        Set keyboard shortcut for action.

        Args:
            action: Action name
            shortcut: Shortcut string (e.g., "Ctrl+Shift+C")

        Returns:
            Tuple[bool, str]: (success, error_message)
        """
        # Validate action
        if action not in DEFAULT_SHORTCUTS:
            return False, f"Unknown action: {action}"

        # Validate shortcut format
        if not self._validate_shortcut(shortcut):
            return False, f"Invalid shortcut format: {shortcut}"

        # Check for conflicts
        conflicts = self.check_conflicts(shortcut, exclude_action=action)
        if conflicts:
            conflicting_actions = ", ".join(conflicts)
            return False, f"Shortcut conflicts with: {conflicting_actions}"

        # Set shortcut
        self._shortcuts[action] = shortcut
        self._save_shortcuts()

        logger.info(f"Shortcut updated: {action} = {shortcut}")
        return True, ""

    def reset_shortcut(self, action: str) -> bool:
        """
        Reset shortcut to default.

        Args:
            action: Action name

        Returns:
            bool: True if reset successfully
        """
        if action not in DEFAULT_SHORTCUTS:
            return False

        self._shortcuts[action] = DEFAULT_SHORTCUTS[action]
        self._save_shortcuts()

        logger.info(f"Shortcut reset to default: {action} = {DEFAULT_SHORTCUTS[action]}")
        return True

    def reset_all_shortcuts(self):
        """Reset all shortcuts to defaults."""
        self._shortcuts = DEFAULT_SHORTCUTS.copy()
        self._save_shortcuts()
        logger.info("All shortcuts reset to defaults")

    def check_conflicts(self, shortcut: str, exclude_action: Optional[str] = None) -> List[str]:
        """
        Check if shortcut conflicts with existing shortcuts.

        Args:
            shortcut: Shortcut to check
            exclude_action: Action to exclude from conflict check

        Returns:
            List[str]: List of conflicting action names
        """
        conflicts = []

        for action, existing_shortcut in self._shortcuts.items():
            if action == exclude_action:
                continue

            if existing_shortcut.lower() == shortcut.lower():
                conflicts.append(action)

        return conflicts

    def _validate_shortcut(self, shortcut: str) -> bool:
        """
        Validate shortcut format.

        Args:
            shortcut: Shortcut string

        Returns:
            bool: True if valid
        """
        if not shortcut:
            return False

        # Basic validation: should contain at least one modifier
        modifiers = ["Ctrl", "Alt", "Shift", "Meta"]
        has_modifier = any(mod in shortcut for mod in modifiers)

        if not has_modifier:
            return False

        # Should contain a key
        parts = shortcut.split("+")
        if len(parts) < 2:
            return False

        return True

    def get_all_shortcuts(self) -> Dict[str, str]:
        """Get all configured shortcuts."""
        return self._shortcuts.copy()

    def get_action_description(self, action: str) -> str:
        """Get human-readable description for action."""
        return ACTION_DESCRIPTIONS.get(action, action.replace("_", " ").title())

    def export_shortcuts(self) -> Dict[str, str]:
        """
        Export shortcuts to dict for backup.

        Returns:
            Dict[str, str]: Shortcuts mapping
        """
        return self._shortcuts.copy()

    def import_shortcuts(self, shortcuts: Dict[str, str]) -> Tuple[int, List[str]]:
        """
        Import shortcuts from dict.

        Args:
            shortcuts: Shortcuts mapping

        Returns:
            Tuple[int, List[str]]: (imported_count, errors)
        """
        imported = 0
        errors = []

        for action, shortcut in shortcuts.items():
            if action not in DEFAULT_SHORTCUTS:
                errors.append(f"Unknown action: {action}")
                continue

            if not self._validate_shortcut(shortcut):
                errors.append(f"Invalid shortcut for {action}: {shortcut}")
                continue

            self._shortcuts[action] = shortcut
            imported += 1

        if imported > 0:
            self._save_shortcuts()
            logger.info(f"Imported {imported} shortcuts")

        return imported, errors


# Singleton instance
keybind_manager = KeybindManager()
