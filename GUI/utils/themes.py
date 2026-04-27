"""
utils/themes.py — Theme management for GlassNote.

Provides light and dark color schemes for consistent UI theming.

Usage:
    from utils.themes import get_theme, apply_theme

    theme = get_theme()  # Gets current theme from config
    widget.setStyleSheet(theme.button_style())
"""

from dataclasses import dataclass
from typing import Dict
from settings import config


@dataclass
class ColorScheme:
    """Color scheme for a theme."""
    # Backgrounds
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str

    # Borders
    border: str
    border_light: str
    divider: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_dim: str

    # Accents
    accent: str
    accent_bg: str
    accent_border: str

    # Status colors
    success: str
    success_bg: str
    success_border: str
    warning: str
    warning_bg: str
    error: str
    error_bg: str

    # Special
    overlay_bg: str
    shadow: str


# ── Theme Definitions ──────────────────────────────────────────────────────────

DARK_THEME = ColorScheme(
    # Backgrounds
    bg_primary="rgba(8, 8, 12, 0.96)",
    bg_secondary="rgba(14, 14, 15, 1)",
    bg_tertiary="rgba(20, 20, 24, 1)",

    # Borders
    border="rgba(255, 255, 255, 0.07)",
    border_light="rgba(255, 255, 255, 0.12)",
    divider="rgba(255, 255, 255, 0.06)",

    # Text
    text_primary="#e8e8e8",
    text_secondary="#d0ddff",
    text_muted="#8888aa",
    text_dim="#5a5a70",

    # Accents
    accent="#5b8ff9",
    accent_bg="rgba(91, 143, 249, 0.13)",
    accent_border="rgba(91, 143, 249, 0.32)",

    # Status
    success="#42d68a",
    success_bg="rgba(66, 214, 138, 0.12)",
    success_border="rgba(66, 214, 138, 0.30)",
    warning="#f5b53f",
    warning_bg="rgba(245, 181, 63, 0.11)",
    error="#f06060",
    error_bg="rgba(240, 96, 96, 0.12)",

    # Special
    overlay_bg="rgba(8, 8, 12, 0.93)",
    shadow="rgba(0, 0, 0, 0.3)",
)


LIGHT_THEME = ColorScheme(
    # Backgrounds
    bg_primary="rgba(255, 255, 255, 0.96)",
    bg_secondary="rgba(248, 248, 250, 1)",
    bg_tertiary="rgba(240, 240, 244, 1)",

    # Borders
    border="rgba(0, 0, 0, 0.08)",
    border_light="rgba(0, 0, 0, 0.12)",
    divider="rgba(0, 0, 0, 0.06)",

    # Text
    text_primary="#1a1a1a",
    text_secondary="#2a2a3a",
    text_muted="#666677",
    text_dim="#9999aa",

    # Accents
    accent="#4a7cf7",
    accent_bg="rgba(74, 124, 247, 0.10)",
    accent_border="rgba(74, 124, 247, 0.30)",

    # Status
    success="#2eb872",
    success_bg="rgba(46, 184, 114, 0.10)",
    success_border="rgba(46, 184, 114, 0.25)",
    warning="#e89f2f",
    warning_bg="rgba(232, 159, 47, 0.10)",
    error="#e74c3c",
    error_bg="rgba(231, 76, 60, 0.10)",

    # Special
    overlay_bg="rgba(255, 255, 255, 0.93)",
    shadow="rgba(0, 0, 0, 0.15)",
)


THEMES: Dict[str, ColorScheme] = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


# ── Theme Access ───────────────────────────────────────────────────────────────

def get_theme(theme_name: str = None) -> ColorScheme:
    """
    Get theme by name or from config.

    Args:
        theme_name: Optional theme name. If None, reads from config.

    Returns:
        ColorScheme: The theme colors
    """
    if theme_name is None:
        theme_name = config.get("theme", "dark")

    return THEMES.get(theme_name, DARK_THEME)


def get_current_theme_name() -> str:
    """Get current theme name from config."""
    return config.get("theme", "dark")


def set_theme(theme_name: str) -> bool:
    """
    Set the current theme.

    Args:
        theme_name: Theme name (dark or light)

    Returns:
        bool: True if theme was set successfully
    """
    if theme_name not in THEMES:
        return False

    config.set("theme", theme_name)
    return True


# ── Style Generators ───────────────────────────────────────────────────────────

def button_style(theme: ColorScheme = None, variant: str = "normal") -> str:
    """
    Generate button stylesheet.

    Args:
        theme: Optional theme. If None, uses current theme.
        variant: Button variant (normal, active, success, warning, error)

    Returns:
        str: Qt stylesheet
    """
    if theme is None:
        theme = get_theme()

    base_color = theme.text_muted
    base_bg = "transparent"
    base_border = "transparent"

    if variant == "active":
        base_color = theme.text_secondary
        base_bg = theme.accent_bg
        base_border = theme.accent_border
    elif variant == "success":
        base_color = theme.success
        base_bg = theme.success_bg
        base_border = theme.success_border
    elif variant == "warning":
        base_color = theme.warning
        base_bg = theme.warning_bg
        base_border = theme.accent_border
    elif variant == "error":
        base_color = theme.error
        base_bg = theme.error_bg
        base_border = theme.error_bg

    return f"""
        QPushButton {{
            background: {base_bg};
            border: 1px solid {base_border};
            color: {base_color};
            font-size: 11px;
            font-weight: 400;
            font-family: 'Segoe UI', 'Inter', sans-serif;
            padding: 3px 9px;
            border-radius: 10px;
            letter-spacing: 0.15px;
        }}
        QPushButton:hover {{
            background: {theme.accent_bg};
            border-color: {theme.accent_border};
            color: {theme.text_secondary};
        }}
        QPushButton:pressed {{
            background: rgba(91,143,249,0.22);
        }}
        QPushButton:disabled {{
            background: transparent;
            color: {theme.text_dim};
            border-color: {theme.divider};
        }}
    """


def panel_style(theme: ColorScheme = None) -> str:
    """Generate panel stylesheet."""
    if theme is None:
        theme = get_theme()

    return f"""
        QWidget {{
            background: {theme.bg_primary};
            border: 1px solid {theme.border};
            border-radius: 12px;
            color: {theme.text_primary};
        }}
    """


def menu_style(theme: ColorScheme = None) -> str:
    """Generate menu stylesheet."""
    if theme is None:
        theme = get_theme()

    return f"""
        QMenu {{
            background: {theme.bg_secondary};
            border: 1px solid {theme.border_light};
            border-radius: 8px;
            padding: 4px;
            color: {theme.text_primary};
            font-family: 'Segoe UI';
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 7px 20px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {theme.bg_tertiary};
            color: {theme.accent};
        }}
        QMenu::separator {{
            height: 1px;
            background: {theme.divider};
            margin: 4px 8px;
        }}
    """


def label_style(theme: ColorScheme = None, variant: str = "normal") -> str:
    """Generate label stylesheet."""
    if theme is None:
        theme = get_theme()

    color = theme.text_primary
    if variant == "muted":
        color = theme.text_muted
    elif variant == "dim":
        color = theme.text_dim
    elif variant == "accent":
        color = theme.accent

    return f"""
        QLabel {{
            color: {color};
            font-family: 'Segoe UI', sans-serif;
        }}
    """


# ── Theme Application ──────────────────────────────────────────────────────────

def apply_theme_to_widget(widget, widget_type: str = "panel"):
    """
    Apply theme to a widget.

    Args:
        widget: QWidget to theme
        widget_type: Type of widget (panel, button, menu, label)
    """
    theme = get_theme()

    if widget_type == "panel":
        widget.setStyleSheet(panel_style(theme))
    elif widget_type == "button":
        widget.setStyleSheet(button_style(theme))
    elif widget_type == "menu":
        widget.setStyleSheet(menu_style(theme))
    elif widget_type == "label":
        widget.setStyleSheet(label_style(theme))
