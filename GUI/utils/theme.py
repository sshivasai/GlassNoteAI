"""
Theme manager — shared dark/light mode system.
FIXED: make_stylesheet now covers ALL child widgets so theme works globally.
"""

from settings import config

DARK = {
    "bg":           "#0e0e0f",
    "bg2":          "#141416",
    "bg3":          "#1e1e22",
    "border":       "#2a2a2e",
    "text":         "#e8e8e8",
    "text2":        "#aaaaaa",
    "text3":        "#666666",
    "accent":       "#4f8ef7",
    "accent_hover": "#3d7de8",
    "danger":       "#e05252",
    "success":      "#4caf78",
    "warn":         "#f7c94f",
    "code_bg":      "rgba(255,255,255,0.04)",
    "code_border":  "rgba(255,255,255,0.08)",
    "overlay_bg":   "rgba(12,12,14,0.96)",
    "pill_bg":      "rgba(14,14,15,0.96)",
}

LIGHT = {
    "bg":           "#f5f5f7",
    "bg2":          "#ffffff",
    "bg3":          "#ebebed",
    "border":       "#d0d0d5",
    "text":         "#111111",
    "text2":        "#555555",
    "text3":        "#999999",
    "accent":       "#2563eb",
    "accent_hover": "#1d4ed8",
    "danger":       "#dc2626",
    "success":      "#16a34a",
    "warn":         "#d97706",
    "code_bg":      "rgba(0,0,0,0.04)",
    "code_border":  "rgba(0,0,0,0.10)",
    "overlay_bg":   "rgba(245,245,247,0.97)",
    "pill_bg":      "rgba(245,245,247,0.97)",
}


def current() -> dict:
    mode = config.get("theme", "dark")
    return DARK if mode == "dark" else LIGHT


def is_dark() -> bool:
    return config.get("theme", "dark") == "dark"


def toggle() -> str:
    new_mode = "light" if is_dark() else "dark"
    config.set("theme", new_mode)
    return new_mode


def set_mode(mode: str):
    config.set("theme", mode)


def make_stylesheet(t: dict) -> str:
    """
    Full QSS stylesheet that covers the window AND all child widgets.
    Using wildcard + class selectors so every nested widget inherits correctly.
    """
    return f"""

/* ── Base — every widget in this window ───────────────────── */
* {{
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: {t['text']};
}}

QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
}}

/* ── Scroll areas & their viewports ──────────────────────── */
QScrollArea {{
    background: {t['bg']};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: {t['bg2']};
}}

QAbstractScrollArea {{
    background: {t['bg2']};
}}

/* ── Input fields ─────────────────────────────────────────── */
QLineEdit {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px 14px;
    color: {t['text']};
    font-size: 13px;
}}

QLineEdit:focus {{
    border: 1px solid {t['accent']};
    background: {t['bg3']};
}}

QTextEdit {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px 14px;
    color: {t['text']};
    font-size: 13px;
    min-height: 80px;
}}

QTextEdit:focus {{
    border: 1px solid {t['accent']};
}}

/* ── Buttons ──────────────────────────────────────────────── */
QPushButton {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 10px 18px;
    color: {t['text']};
    font-size: 13px;
}}

QPushButton:hover {{
    border-color: {t['accent']};
    color: {t['accent']};
    background: {t['bg3']};
}}

QPushButton:pressed {{
    background: {t['bg2']};
}}

QPushButton#primary {{
    background: {t['accent']};
    border: none;
    color: white;
    font-weight: 600;
    font-size: 14px;
    padding: 12px 24px;
    border-radius: 8px;
}}

QPushButton#primary:hover {{
    background: {t['accent_hover']};
}}

QPushButton#primary:pressed {{
    background: {t['accent_hover']};
}}

QPushButton#ghost {{
    background: transparent;
    border: none;
    color: {t['text3']};
    font-size: 12px;
}}

QPushButton#ghost:hover {{
    color: {t['text2']};
    background: transparent;
}}

QPushButton#danger {{
    background: transparent;
    border: 1px solid {t['danger']};
    color: {t['danger']};
}}

QPushButton#danger:hover {{
    background: {t['danger']};
    color: white;
}}

/* ── ComboBox ─────────────────────────────────────────────── */
QComboBox {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 8px 12px;
    color: {t['text']};
    font-size: 13px;
    min-width: 180px;
}}

QComboBox:focus {{
    border: 1px solid {t['accent']};
}}

QComboBox:hover {{
    border-color: {t['accent']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
    background: transparent;
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    color: {t['text']};
    selection-background-color: {t['bg2']};
    selection-color: {t['accent']};
    padding: 4px;
    outline: none;
}}

/* ── CheckBox ─────────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {t['text2']};
    background: transparent;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid {t['border']};
    background: {t['bg3']};
}}

QCheckBox::indicator:checked {{
    background: {t['accent']};
    border-color: {t['accent']};
}}

QCheckBox::indicator:hover {{
    border-color: {t['accent']};
}}

/* ── Spin boxes ───────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 7px 10px;
    color: {t['text']};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {t['accent']};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {t['bg3']};
    border: none;
    width: 16px;
}}

/* ── Labels ───────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {t['text']};
}}

QLabel#field_label {{
    color: {t['text3']};
    font-size: 11px;
    letter-spacing: 0.8px;
    font-weight: 600;
    background: transparent;
}}

QLabel#section {{
    color: {t['text3']};
    font-size: 11px;
    letter-spacing: 1px;
    font-weight: 600;
    padding-top: 8px;
    background: transparent;
}}

QLabel#error {{
    color: {t['danger']};
    font-size: 12px;
    background: transparent;
}}

QLabel#value_label {{
    color: {t['accent']};
    font-size: 12px;
    min-width: 42px;
    background: transparent;
}}

/* ── Frames / separators ──────────────────────────────────── */
QFrame#separator, QFrame#h_sep {{
    background: {t['border']};
    max-height: 1px;
    border: none;
}}

/* ── Scroll bars ──────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {t['bg2']};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t['text3']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}

QScrollBar:horizontal {{
    background: {t['bg2']};
    height: 6px;
    border-radius: 3px;
}}

QScrollBar::handle:horizontal {{
    background: {t['border']};
    border-radius: 3px;
    min-width: 20px;
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

/* ── Tab widget ───────────────────────────────────────────── */
QTabWidget {{
    background: {t['bg2']};
}}

QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: 8px;
    background: {t['bg2']};
    top: -1px;
}}

QTabBar {{
    background: {t['bg']};
}}

QTabBar::tab {{
    background: {t['bg3']};
    color: {t['text3']};
    padding: 8px 16px;
    border: none;
    font-size: 12px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background: {t['bg2']};
    color: {t['text']};
    border-bottom: 2px solid {t['accent']};
}}

QTabBar::tab:hover {{
    color: {t['text2']};
    background: {t['bg2']};
}}

/* ── Slider ───────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {t['border']};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {t['accent']};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}

QSlider::sub-page:horizontal {{
    background: {t['accent']};
    border-radius: 2px;
}}

/* ── Stacked widget pages ─────────────────────────────────── */
QStackedWidget {{
    background: {t['bg']};
}}

/* ── Menu (tray context menu) ─────────────────────────────── */
QMenu {{
    background: {t['bg3']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    padding: 4px;
    color: {t['text']};
}}

QMenu::item {{
    padding: 7px 20px;
    border-radius: 4px;
    background: transparent;
}}

QMenu::item:selected {{
    background: {t['bg2']};
    color: {t['accent']};
}}

QMenu::separator {{
    height: 1px;
    background: {t['border']};
    margin: 4px 8px;
}}
"""


def theme_btn_style(t: dict) -> str:
    return f"""
        QPushButton {{
            background: {t['bg3']};
            border: 1px solid {t['border']};
            border-radius: 14px;
            color: {t['text2']};
            font-size: 13px;
            padding: 3px 10px;
            min-width: 56px;
        }}
        QPushButton:hover {{
            border-color: {t['accent']};
            color: {t['accent']};
        }}
    """