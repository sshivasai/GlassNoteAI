"""
Theme manager — shared dark/light mode system.
FIXED: make_stylesheet now covers ALL child widgets so theme works globally.
"""

from settings import config

DARK = {
    "bg":           "#090b10",
    "bg2":          "#10141d",
    "bg3":          "#171d29",
    "border":       "#273041",
    "text":         "#f4f7fb",
    "text2":        "#aab6c8",
    "text3":        "#738095",
    "accent":       "#38bdf8",
    "accent_hover": "#0ea5e9",
    "danger":       "#fb7185",
    "danger_dim":   "rgba(251,113,133,0.12)",
    "success":      "#34d399",
    "warn":         "#fbbf24",
    "code_bg":      "rgba(56,189,248,0.08)",
    "code_border":  "rgba(56,189,248,0.16)",
    "overlay_bg":   "rgba(9,11,16,0.96)",
    "pill_bg":      "rgba(9,11,16,0.96)",
}

LIGHT = {
    "bg":           "#f7f9fc",
    "bg2":          "#ffffff",
    "bg3":          "#eef3f8",
    "border":       "#d8e0ea",
    "text":         "#111827",
    "text2":        "#526071",
    "text3":        "#8995a6",
    "accent":       "#0284c7",
    "accent_hover": "#0369a1",
    "danger":       "#e11d48",
    "danger_dim":   "rgba(225,29,72,0.08)",
    "success":      "#059669",
    "warn":         "#b45309",
    "code_bg":      "rgba(2,132,199,0.08)",
    "code_border":  "rgba(2,132,199,0.16)",
    "overlay_bg":   "rgba(247,249,252,0.97)",
    "pill_bg":      "rgba(255,255,255,0.97)",
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
    padding: 9px 16px;
    color: {t['text']};
    font-size: 13px;
    font-weight: 500;
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
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding: 11px 22px;
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
    border: 1px solid {t['border']};
    color: {t['text2']};
    font-size: 13px;
}}

QPushButton#ghost:hover {{
    color: {t['accent']};
    border-color: {t['accent']};
    background: {t['code_bg']};
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
    border: none;
    background: {t['bg2']};
    top: -1px;
}}

QTabBar {{
    background: {t['bg']};
}}

QTabBar::tab {{
    background: transparent;
    color: {t['text3']};
    padding: 10px 16px;
    border: none;
    font-size: 12px;
    font-weight: 600;
    margin-right: 1px;
}}

QTabBar::tab:selected {{
    background: {t['code_bg']};
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
            border-radius: 8px;
            color: {t['text2']};
            font-size: 13px;
            padding: 0;
        }}
        QPushButton:hover {{
            border-color: {t['accent']};
            color: {t['accent']};
            background: {t['code_bg']};
        }}
    """
