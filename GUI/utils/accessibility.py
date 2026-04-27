"""
utils/accessibility.py — Accessibility features for GlassNote.

Provides:
  - Screen reader support
  - Keyboard-only navigation
  - High contrast mode
  - Configurable font sizes

Usage:
    from utils.accessibility import apply_accessibility_features

    apply_accessibility_features(widget, accessible_name="Capture Button")
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor
from settings import config
from utils.logger import get_logger

logger = get_logger(__name__)


def apply_accessibility_features(
    widget: QWidget,
    accessible_name: str = "",
    accessible_description: str = "",
    role: str = "button",
):
    """
    Apply accessibility features to a widget.

    Args:
        widget: Widget to make accessible
        accessible_name: Name for screen readers
        accessible_description: Detailed description
        role: Widget role (button, label, textbox, etc.)
    """
    # Set accessible name and description
    if accessible_name:
        widget.setAccessibleName(accessible_name)

    if accessible_description:
        widget.setAccessibleDescription(accessible_description)

    # Enable focus for keyboard navigation
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # Set tab order (caller should use QWidget.setTabOrder for sequences)

    logger.debug(f"Accessibility applied: {accessible_name}")


def enable_high_contrast_mode(widget: QWidget):
    """
    Enable high contrast mode for a widget.

    Args:
        widget: Root widget to apply high contrast
    """
    cfg = config.load_config()
    if not cfg.get("high_contrast_mode", False):
        return

    # High contrast palette
    palette = QPalette()

    # Background: Pure black
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0))

    # Text: Pure white
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))

    # Buttons: High contrast
    palette.setColor(QPalette.ColorRole.Button, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))

    # Highlights: Bright yellow
    palette.setColor(QPalette.ColorRole.Highlight, QColor(255, 255, 0))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    widget.setPalette(palette)
    logger.info("High contrast mode enabled")


def set_font_scale(widget: QWidget, scale: float = 1.0):
    """
    Scale font size for better readability.

    Args:
        widget: Widget to scale fonts
        scale: Scale factor (1.0 = normal, 1.5 = 150%, etc.)
    """
    cfg = config.load_config()
    scale = cfg.get("font_scale", 1.0)

    if scale == 1.0:
        return  # No scaling needed

    # Apply to widget and all children
    for child in widget.findChildren(QWidget):
        font = child.font()
        font.setPointSizeF(font.pointSizeF() * scale)
        child.setFont(font)

    logger.info(f"Font scale applied: {scale}x")


def enable_keyboard_navigation_hints(widget: QWidget):
    """
    Show keyboard navigation hints.

    Args:
        widget: Root widget
    """
    # Enable keyboard focus visual hints
    widget.setStyleSheet("""
        *:focus {
            outline: 2px solid #5b8ff9;
            outline-offset: 2px;
        }
    """)


# ── Screen Reader Helpers ──────────────────────────────────────────────────────

def announce_to_screen_reader(widget: QWidget, message: str):
    """
    Announce a message to screen readers.

    Args:
        widget: Widget context
        message: Message to announce
    """
    # Qt doesn't have direct screen reader API, but accessible description
    # changes can trigger announcements
    widget.setAccessibleDescription(message)


# ── Configuration ──────────────────────────────────────────────────────────────

def is_accessibility_enabled() -> bool:
    """Check if any accessibility features are enabled."""
    cfg = config.load_config()
    return (
        cfg.get("high_contrast_mode", False) or
        cfg.get("font_scale", 1.0) != 1.0 or
        cfg.get("screen_reader_support", False)
    )


def apply_all_accessibility_features(root_widget: QWidget):
    """
    Apply all enabled accessibility features to app.

    Args:
        root_widget: Root application widget
    """
    cfg = config.load_config()

    if cfg.get("high_contrast_mode", False):
        enable_high_contrast_mode(root_widget)

    font_scale = cfg.get("font_scale", 1.0)
    if font_scale != 1.0:
        set_font_scale(root_widget, font_scale)

    if cfg.get("keyboard_navigation_hints", False):
        enable_keyboard_navigation_hints(root_widget)

    logger.info("Accessibility features applied")
