import os
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QComboBox,
    QCheckBox, QFrame, QStackedWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from session.manager import manager
from session import resume_parser
from settings import config
from utils import theme as th
import pricing_config as pricing


# ── Small helpers ─────────────────────────────────────────────────────────────

def field_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("field_label")
    return lbl


def sep() -> QFrame:
    f = QFrame()
    f.setObjectName("separator")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


# ── Drop zone ─────────────────────────────────────────────────────────────────

class DropZone(QWidget):
    """
    A custom widget that accepts drag-and-drop events for PDF and DOCX files.
    Allows the user to easily load a resume for context parsing.
    """
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(80)
        self._file = ""
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel("Drop PDF / DOCX here or click to browse")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def apply_theme(self, t: dict):
        self.setStyleSheet(f"""
            QWidget {{
                background: {t['bg3']};
                border: 1.5px dashed {t['border']};
                border-radius: 8px;
                color: {t['text3']};
            }}
            QWidget:hover {{ border-color: {t['accent']}; }}
        """)
        if self._file:
            self._label.setStyleSheet(
                f"color:{t['accent']}; font-size:12px;"
                f"border:none; background:transparent;"
            )
        else:
            self._label.setStyleSheet(
                f"color:{t['text3']}; font-size:12px;"
                f"border:none; background:transparent;"
            )

    def mousePressEvent(self, e):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Resume", "", "Documents (*.pdf *.docx *.doc)"
        )
        if path:
            self._set_file(path)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            self._set_file(urls[0].toLocalFile())

    def _set_file(self, path: str):
        self._file = path
        self._label.setText(f"📄  {os.path.basename(path)}")
        t = th.current()
        self._label.setStyleSheet(
            f"color:{t['accent']}; font-size:12px;"
            f"border:none; background:transparent;"
        )
        self.file_selected.emit(path)

    def get_file(self) -> str:
        return self._file


# ── Main setup window ─────────────────────────────────────────────────────────

class SessionSetupWindow(QWidget):
    """
    The main UI window for configuring and starting a new GlassNote session.

    Fixed session start flow (BUG-2, BUG-7, PERF-4):
    1. User clicks "Start Session"
    2. Background thread: GET /api/auth/me  → verify plan
    3. Background thread: POST /api/sessions/start → register with backend
       - 402 → show quota-exceeded error with upgrade CTA, stay on page (UX-1)
       - network error → show graceful error, stay on page (UX-5)
    4. Only on success: emit session_started, close window
    5. app_controller._on_session_started() starts audio pipeline warm-up (BUG-6)
    """
    session_started = pyqtSignal()
    open_settings   = pyqtSignal()

    # Internal signals for safe thread→UI bridge
    _sig_plan_update  = pyqtSignal(str, int, int)   # plan, sessions_used, sessions_remaining
    _sig_verify_error = pyqtSignal(str)              # fatal error message
    _sig_session_ok   = pyqtSignal(str)              # backend session_id
    _sig_session_err  = pyqtSignal(str, bool)        # message, is_quota_error

    # Spinner frames for animated loading indicator (UX-3, PERF-3)
    _SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Colour tokens used only inside this file
    _DARK = {
        "win_bg":       "#0d0d10",
        "title_bg":     "#111115",
        "title_border": "#1e1e24",
        "body_bg":      "#0d0d10",
        "text":         "#e0e0e8",
        "text2":        "#888",
        "text3":        "#555",
        "accent":       "#4f8ef7",
        "accent_dim":   "rgba(79,142,247,0.12)",
        "accent_brd":   "rgba(79,142,247,0.35)",
        "danger":       "#e05252",
        "danger_dim":   "rgba(224,82,82,0.10)",
        "success":      "#4cca7e",
        "warning":      "#f59e0b",
        "border":       "#1e1e24",
        "input_bg":     "#17171c",
        "input_brd":    "#252530",
        "sep":          "#1a1a22",
        "close_icon":   "#666",
        "settings_icon":"#666",
    }
    _LIGHT = {
        "win_bg":       "#f5f5f8",
        "title_bg":     "#eeeef4",
        "title_border": "#d8d8e0",
        "body_bg":      "#f5f5f8",
        "text":         "#18181e",
        "text2":        "#555",
        "text3":        "#888",
        "accent":       "#2563eb",
        "accent_dim":   "rgba(37,99,235,0.08)",
        "accent_brd":   "rgba(37,99,235,0.30)",
        "danger":       "#dc2626",
        "danger_dim":   "rgba(220,38,38,0.08)",
        "success":      "#16a34a",
        "warning":      "#d97706",
        "border":       "#d4d4de",
        "input_bg":     "#ffffff",
        "input_brd":    "#d0d0da",
        "sep":          "#e0e0ea",
        "close_icon":   "#999",
        "settings_icon":"#999",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._resume_text      = ""
        self._drag_pos         = None
        self._pending_provider = ""
        self._pending_model    = ""
        self._pending_cfg      = {}
        self._pending_plan     = ""
        self._spinner_frame    = 0
        self._spinner_phase    = ""
        self._spinner_timer: QTimer | None = None

        # Wire internal signals (always executes on main thread)
        self._sig_plan_update.connect(self._on_plan_update)
        self._sig_verify_error.connect(self._on_verify_error)
        self._sig_session_ok.connect(self._on_session_registered)
        self._sig_session_err.connect(self._on_session_error)
        self._build_ui()
        self._refresh_theme()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Constructs the multi-step UI layout for the session configuration."""
        self.setWindowTitle("GlassNote — New Session")
        self.setFixedWidth(500)
        self.setFont(QFont("Segoe UI", 11))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title_bar = self._build_title_bar()
        root.addWidget(self._title_bar)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_page1())
        self.stack.addWidget(self._build_page2())
        root.addWidget(self.stack)

    # ── Title bar ─────────────────────────────────────────────────────────────

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("title_bar")
        bar.setFixedHeight(52)

        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 0, 10, 0)
        row.setSpacing(6)

        import os
        from PyQt6.QtGui import QPixmap
        _logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Logo.png")
        self._icon_lbl = QLabel()
        self._icon_lbl.setObjectName("icon_label")
        _px = QPixmap(_logo)
        if not _px.isNull():
            self._icon_lbl.setPixmap(_px.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
        else:
            self._icon_lbl.setText("◈")
        row.addWidget(self._icon_lbl)

        self._title_lbl = QLabel("New Session")
        self._title_lbl.setObjectName("title_label")
        row.addWidget(self._title_lbl)

        row.addStretch()

        self.step_label = QLabel("STEP 1 OF 2")
        self.step_label.setObjectName("step_label")
        row.addWidget(self.step_label)

        row.addSpacing(8)

        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setObjectName("settings_btn")
        self._btn_settings.setFixedSize(32, 32)
        self._btn_settings.setToolTip("Open Settings")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self.open_settings)
        row.addWidget(self._btn_settings)

        row.addSpacing(2)

        self._btn_theme = QPushButton("☀" if th.is_dark() else "🌙")
        self._btn_theme.setObjectName("theme_btn")
        self._btn_theme.setFixedSize(32, 32)
        self._btn_theme.setToolTip("Toggle dark / light")
        self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theme.clicked.connect(self._toggle_theme)
        row.addWidget(self._btn_theme)

        row.addSpacing(2)

        self._btn_close = QPushButton("✕")
        self._btn_close.setObjectName("close_btn")
        self._btn_close.setFixedSize(32, 32)
        self._btn_close.setToolTip("Close")
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.close)
        row.addWidget(self._btn_close)

        return bar

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _build_page1(self) -> QWidget:
        outer  = QWidget(); outer.setObjectName("page_outer")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("page_scroll")

        self._page1_inner = QWidget()
        self._page1_inner.setObjectName("page_inner")

        lay = QVBoxLayout(self._page1_inner)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        lay.addWidget(field_label("Company"))
        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("e.g. Google, Microsoft, Amazon…")
        lay.addWidget(self.company_input)

        lay.addWidget(field_label("Job Description"))
        self.jd_input = QTextEdit()
        self.jd_input.setPlaceholderText("Paste the job description here…")
        self.jd_input.setFixedHeight(100)
        lay.addWidget(self.jd_input)

        lay.addWidget(field_label("Resume (Optional)"))
        self.drop_zone = DropZone()
        self.drop_zone.file_selected.connect(self._parse_resume)
        lay.addWidget(self.drop_zone)

        self.resume_status = QLabel("")
        self.resume_status.setObjectName("status_lbl")
        lay.addWidget(self.resume_status)

        lay.addStretch()

        nav = QHBoxLayout()
        nav.addStretch()
        btn_next = QPushButton("Next  →")
        btn_next.setObjectName("primary")
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.clicked.connect(self._go_page2)
        nav.addWidget(btn_next)
        lay.addLayout(nav)

        scroll.setWidget(self._page1_inner)
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)
        ol.addWidget(scroll)
        return outer

    def _build_page2(self) -> QWidget:
        outer  = QWidget(); outer.setObjectName("page_outer")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("page_scroll")

        self._page2_inner = QWidget()
        self._page2_inner.setObjectName("page_inner")

        lay = QVBoxLayout(self._page2_inner)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        # Language row
        lang_row = QHBoxLayout()

        lc = QVBoxLayout(); lc.setSpacing(6)
        lc.addWidget(field_label("Language"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "English", "Hindi", "Spanish", "French",
            "German", "Mandarin", "Arabic",
        ])
        lc.addWidget(self.lang_combo)
        lang_row.addLayout(lc)

        lang_row.addSpacing(20)

        sc = QVBoxLayout(); sc.setSpacing(6)
        sc.addWidget(field_label("Simple Language"))
        self.simple_lang = QCheckBox("Enable")
        sc.addWidget(self.simple_lang)
        lang_row.addLayout(sc)
        lang_row.addStretch()
        lay.addLayout(lang_row)

        lay.addWidget(sep())

        # ── Plan info banner (UX-2, UX-4) ────────────────────────────
        self._plan_info = QLabel("")
        self._plan_info.setObjectName("status_lbl")
        self._plan_info.setWordWrap(True)
        lay.addWidget(self._plan_info)

        lay.addWidget(sep())

        lay.addWidget(field_label("AI Model"))
        self.model_combo = QComboBox()
        self._populate_models()
        lay.addWidget(self.model_combo)

        lay.addWidget(sep())

        lay.addWidget(field_label("Extra Instructions (Optional)"))
        self.extra_input = QTextEdit()
        self.extra_input.setPlaceholderText(
            "e.g. Focus on Python. Keep answers short. Emphasize patterns…"
        )
        self.extra_input.setFixedHeight(90)
        lay.addWidget(self.extra_input)

        # Error label (word-wrapped for long quota messages)
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_lbl")
        self.error_label.setWordWrap(True)
        lay.addWidget(self.error_label)

        lay.addStretch()

        nav = QHBoxLayout()
        # BUG-4 fix: store direct reference instead of using findChild
        self._btn_back = QPushButton("← Back")
        self._btn_back.setObjectName("ghost")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self._go_page1)
        nav.addWidget(self._btn_back)
        nav.addStretch()
        # BUG-4 fix: direct reference to start button
        self._btn_start = QPushButton("Start Session")
        self._btn_start.setObjectName("primary")
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.clicked.connect(self._start_session)
        nav.addWidget(self._btn_start)
        lay.addLayout(nav)

        scroll.setWidget(self._page2_inner)
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)
        ol.addWidget(scroll)
        return outer

    def _populate_models(self, sessions_used: int = -1, sessions_remaining: int = -1):
        """
        Populate model dropdown filtered by the user's plan.

        Args:
            sessions_used: How many sessions used this period (-1 = unknown).
            sessions_remaining: How many sessions left (-1 = unlimited/unknown).
        """
        self.model_combo.clear()

        cfg     = config.load_config()
        plan_id = cfg.get("glassnote_user_plan", "").strip() or "free"

        allowed   = pricing.get_allowed_models(plan_id)
        plan_data = pricing.get_plan(plan_id)

        self._model_map = allowed
        for display, _, _ in allowed:
            self.model_combo.addItem(display)

        # Build sessions remaining string (UX-2, UX-4)
        limit_num    = plan_data["sessions_per_month"]
        is_unlimited = (limit_num >= 9999)
        dur_limit    = pricing.format_duration(plan_data["session_duration_minutes"])
        plan_name    = plan_data["display_name"]
        t            = self._tok()

        if is_unlimited:
            remaining_str = "Unlimited sessions"
            info_color    = t["success"]
        elif sessions_remaining == 0:
            remaining_str = "⚠ No sessions remaining — upgrade to continue"
            info_color    = t["danger"]
        elif sessions_remaining == 1:
            remaining_str = "⚠ Last session remaining"
            info_color    = t["warning"]
        elif sessions_remaining > 0:
            remaining_str = f"{sessions_remaining} sessions remaining"
            info_color    = t["success"] if sessions_remaining > 2 else t["warning"]
        elif sessions_used >= 0:
            remaining_str = f"{sessions_used}/{limit_num} sessions used"
            info_color    = t["text2"]
        else:
            sess_limit    = pricing.format_sessions(limit_num)
            remaining_str = f"{sess_limit} sessions"
            info_color    = t["text2"]

        if plan_id == "free":
            banner = (
                f"✅ {plan_name} Plan  •  {remaining_str}  •  {dur_limit} each\n"
                f"   {len(allowed)} model{'s' if len(allowed) != 1 else ''} available  •  Upgrade for more"
            )
        elif plan_data["session_duration_minutes"] > 0:
            banner = (
                f"✅ {plan_name} Plan  •  {remaining_str}  •  {dur_limit} each\n"
                f"   {len(allowed)} models available"
            )
        else:
            banner = (
                f"✅ {plan_name} Plan  •  {remaining_str}\n"
                f"   All {len(allowed)} models available"
            )

        self._plan_info.setText(banner)
        self._plan_info.setStyleSheet(f"color: {info_color}; font-size: 12px;")

    def _get_selected_provider_model(self):
        idx = self.model_combo.currentIndex()
        if 0 <= idx < len(self._model_map):
            _, provider, model = self._model_map[idx]
            return provider, model
        return "anthropic", "claude-haiku-4-5"

    # ── Theme ──────────────────────────────────────────────────────────────────

    def _tok(self) -> dict:
        return self._DARK if th.is_dark() else self._LIGHT

    def _refresh_theme(self):
        t = self._tok()

        self.setStyleSheet(f"""
            QWidget {{
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QWidget#page_outer {{
                background: {t['win_bg']};
            }}
            QWidget#page_inner {{
                background: {t['win_bg']};
            }}
            QScrollArea#page_scroll {{
                background: {t['win_bg']};
                border: none;
            }}
            QScrollArea#page_scroll > QWidget > QWidget {{
                background: {t['win_bg']};
            }}
            QLabel#field_label {{
                color: {t['text3']};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
                margin-bottom: 2px;
            }}
            QLabel#status_lbl {{
                font-size: 12px;
                color: {t['text2']};
            }}
            QLabel#error_lbl {{
                font-size: 12px;
                color: {t['danger']};
            }}
            QLineEdit, QTextEdit {{
                background: {t['input_bg']};
                border: 1px solid {t['input_brd']};
                border-radius: 7px;
                color: {t['text']};
                font-size: 12px;
                padding: 7px 10px;
                selection-background-color: {t['accent_dim']};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {t['accent']};
            }}
            QLineEdit::placeholder {{ color: {t['text3']}; }}
            QComboBox {{
                background: {t['input_bg']};
                border: 1px solid {t['input_brd']};
                border-radius: 7px;
                color: {t['text']};
                font-size: 12px;
                padding: 6px 10px;
                min-height: 28px;
            }}
            QComboBox:focus {{ border-color: {t['accent']}; }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {t['text2']};
                width: 0; height: 0;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background: {t['input_bg']};
                border: 1px solid {t['input_brd']};
                color: {t['text']};
                selection-background-color: {t['accent_dim']};
                selection-color: {t['accent']};
                outline: none;
            }}
            QCheckBox {{
                color: {t['text']};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border-radius: 4px;
                border: 1.5px solid {t['input_brd']};
                background: {t['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {t['accent']};
                border-color: {t['accent']};
            }}
            QFrame#separator {{
                background: {t['sep']};
                max-height: 1px;
                border: none;
            }}
            QPushButton#primary {{
                background: {t['accent']};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 22px;
                min-height: 34px;
            }}
            QPushButton#primary:hover {{
                background: rgba(79,142,247,0.85);
            }}
            QPushButton#primary:pressed {{
                background: rgba(79,142,247,0.70);
            }}
            QPushButton#primary:disabled {{
                background: rgba(79,142,247,0.40);
                color: rgba(255,255,255,0.55);
            }}
            QPushButton#ghost {{
                background: transparent;
                border: 1px solid {t['border']};
                border-radius: 8px;
                color: {t['text2']};
                font-size: 12px;
                padding: 8px 18px;
                min-height: 34px;
            }}
            QPushButton#ghost:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
                background: {t['accent_dim']};
            }}
            QPushButton#ghost:disabled {{
                color: {t['text3']};
                border-color: {t['sep']};
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']};
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t['text3']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        self._title_bar.setStyleSheet(f"""
            QWidget#title_bar {{
                background: {t['title_bg']};
                border-bottom: 1px solid {t['title_border']};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
        """)

        self._icon_lbl.setStyleSheet(
            f"color:{t['accent']}; font-size:18px;"
            f"border:none; background:transparent;"
        )
        self._title_lbl.setStyleSheet(
            f"color:{t['text']}; font-size:14px; font-weight:600;"
            f"margin-left:4px; border:none; background:transparent;"
        )
        self.step_label.setStyleSheet(
            f"color:{t['text3']}; font-size:10px; letter-spacing:1px;"
            f"border:none; background:transparent;"
        )
        self._btn_settings.setStyleSheet(f"""
            QPushButton#settings_btn {{
                background: transparent;
                border: 1px solid {t['border']};
                border-radius: 8px;
                color: {t['settings_icon']};
                font-size: 15px;
            }}
            QPushButton#settings_btn:hover {{
                color: {t['accent']};
                background: {t['accent_dim']};
                border-color: {t['accent_brd']};
            }}
            QPushButton#settings_btn:pressed {{
                background: rgba(79,142,247,0.18);
            }}
        """)
        self._btn_theme.setStyleSheet(f"""
            QPushButton#theme_btn {{
                background: transparent;
                border: 1px solid {t['border']};
                border-radius: 8px;
                color: {t['text2']};
                font-size: 15px;
            }}
            QPushButton#theme_btn:hover {{
                color: {t['accent']};
                background: {t['accent_dim']};
                border-color: {t['accent_brd']};
            }}
        """)
        self._btn_theme.setText("☀" if th.is_dark() else "🌙")
        self._btn_close.setStyleSheet(f"""
            QPushButton#close_btn {{
                background: rgba(224,82,82,0.12);
                border: 1px solid rgba(224,82,82,0.25);
                border-radius: 8px;
                color: {t['danger']};
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton#close_btn:hover {{
                background: {t['danger']};
                border-color: {t['danger']};
                color: white;
            }}
            QPushButton#close_btn:pressed {{
                background: rgba(224,82,82,0.70);
            }}
        """)

        if hasattr(self, "drop_zone"):
            self.drop_zone.apply_theme({
                "bg3":   t["input_bg"],
                "border":t["border"],
                "text3": t["text3"],
                "accent":t["accent"],
            })

        if hasattr(self, "_page1_inner"):
            self._page1_inner.setStyleSheet(
                f"QWidget#page_inner {{ background: {t['win_bg']}; }}"
            )
        if hasattr(self, "_page2_inner"):
            self._page2_inner.setStyleSheet(
                f"QWidget#page_inner {{ background: {t['win_bg']}; }}"
            )

    def _toggle_theme(self):
        th.toggle()
        self._refresh_theme()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _parse_resume(self, path: str):
        t = self._tok()
        self.resume_status.setText("Parsing resume...")
        try:
            self._resume_text = resume_parser.extract_text(path)
            self.resume_status.setText(
                f"Resume loaded ({len(self._resume_text)} chars)"
            )
            self.resume_status.setStyleSheet(
                f"color:{t['success']}; font-size:12px;"
            )
        except Exception as e:
            self._resume_text = ""
            self.resume_status.setText(f"Error: {e}")
            self.resume_status.setStyleSheet(
                f"color:{t['danger']}; font-size:12px;"
            )

    def _open_inline_login(self):
        from api.login_ui import LoginWindow
        self._login_win = LoginWindow()
        self._login_win.authenticated.connect(self._on_inline_auth)
        self._login_win.show()

    def _on_inline_auth(self, email: str, plan: str):
        self.error_label.setText("")
        if hasattr(self, "_inline_signin_btn"):
            self._inline_signin_btn.hide()
        self._populate_models()

    def _go_page2(self):
        self.stack.setCurrentIndex(1)
        self.step_label.setText("STEP 2 OF 2")
        self.adjustSize()
        # Fetch live quota when user reaches page 2 (UX-2, UX-4)
        self._fetch_quota_for_banner()

    def _go_page1(self):
        self.stack.setCurrentIndex(0)
        self.step_label.setText("STEP 1 OF 2")
        self.adjustSize()

    def _fetch_quota_for_banner(self):
        """
        Fetch live quota from /api/auth/me in background and update the
        plan info banner with real sessions_remaining count (UX-2, UX-4).
        Non-blocking — banner updates when response arrives.
        """
        cfg   = config.load_config()
        token = self._get_token(cfg)
        if not token:
            return
        api_url = cfg.get("glassnote_api_url", "").rstrip("/")
        if not api_url:
            return
        import httpx, threading

        def _fetch():
            try:
                with httpx.Client(http2=True, timeout=httpx.Timeout(5.0, connect=3.0)) as c:
                    r = c.get(
                        f"{api_url}/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                if r.status_code == 200:
                    data      = r.json()
                    used      = data.get("sessions_used", -1)
                    remaining = data.get("sessions_remaining", -1)
                    plan      = data.get("plan", "free")
                    cfg2 = config.load_config()
                    cfg2["glassnote_user_plan"] = plan
                    config.save_config(cfg2)
                    self._sig_plan_update.emit(plan, used, remaining)
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True, name="quota-banner").start()

    @staticmethod
    def _get_token(cfg: dict) -> str:
        """Load token from keyring or config fallback."""
        from api.auth_client import _keyring_load
        return _keyring_load() or cfg.get("glassnote_api_token", "").strip()

    # ── Loading animation ─────────────────────────────────────────────────────

    def _set_loading(self, loading: bool, phase: str = ""):
        """
        Toggle the loading state of the Start Session button (UX-3, PERF-3).
        When loading=True: animated spinner + phase text, buttons disabled.
        When loading=False: restores label, re-enables buttons (BUG-5 fix).
        """
        if loading:
            self._btn_start.setEnabled(False)
            self._btn_back.setEnabled(False)
            self._spinner_frame = 0
            self._spinner_phase = phase
            if self._spinner_timer is None:
                self._spinner_timer = QTimer(self)
                self._spinner_timer.setInterval(80)
                self._spinner_timer.timeout.connect(self._tick_spinner)
            self._spinner_timer.start()
            self._tick_spinner()
        else:
            if self._spinner_timer:
                self._spinner_timer.stop()
            self._btn_start.setText("Start Session")
            self._btn_start.setEnabled(True)
            self._btn_back.setEnabled(True)

    def _tick_spinner(self):
        frame = self._SPINNER[self._spinner_frame % len(self._SPINNER)]
        phase = getattr(self, "_spinner_phase", "")
        self._btn_start.setText(f"{frame}  {phase}" if phase else frame)
        self._spinner_frame += 1

    # ── Session start ─────────────────────────────────────────────────────────

    def _start_session(self):
        """
        Start session with server-side plan verification + session registration.

        Fixed flow (BUG-2, BUG-7, PERF-4):
        1. Check for stored JWT token
        2. Background: GET /api/auth/me -> verify plan + live quota
        3. Background: POST /api/sessions/start -> register session
           - 402 -> show quota-exceeded error with upgrade CTA (UX-1)
           - network error -> show graceful error (UX-5)
        4. Only on success: emit session_started, close window
        5. Audio pipeline warm-up happens AFTER this in app_controller (BUG-6)
        """
        provider, model_id = self._get_selected_provider_model()
        cfg = config.load_config()
        t   = self._tok()

        token = self._get_token(cfg)
        if not token:
            self.error_label.setStyleSheet(f"color: {t['danger']}; font-size: 12px;")
            self.error_label.setText("Please sign in to start a session.")
            if not hasattr(self, "_inline_signin_btn"):
                self._inline_signin_btn = QPushButton("Sign In to GlassNote")
                self._inline_signin_btn.setObjectName("primary")
                self._inline_signin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self._inline_signin_btn.clicked.connect(self._open_inline_login)
                self.error_label.parent().layout().addWidget(self._inline_signin_btn)
            self._inline_signin_btn.show()
            return
        if hasattr(self, "_inline_signin_btn"):
            self._inline_signin_btn.hide()

        api_url = cfg.get("glassnote_api_url", "http://localhost:8000").rstrip("/")
        self.error_label.setText("")
        self._set_loading(True, "Verifying plan...")
        self._pending_provider = provider
        self._pending_model    = model_id
        self._pending_cfg      = cfg

        import httpx, threading

        def _verify_and_register():
            """
            Phase 1: GET /api/auth/me — verify plan + live quota.
            Phase 2: POST /api/sessions/start — register session (PERF-4).
            Both in the same background thread — one round-trip saved.
            """
            server_plan        = None
            sessions_used      = -1
            sessions_remaining = -1
            try:
                with httpx.Client(http2=True, timeout=httpx.Timeout(8.0, connect=4.0)) as c:
                    r = c.get(
                        f"{api_url}/api/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                if r.status_code == 200:
                    data               = r.json()
                    server_plan        = data.get("plan", "free")
                    sessions_used      = data.get("sessions_used", -1)
                    sessions_remaining = data.get("sessions_remaining", -1)
                    cfg2 = config.load_config()
                    cfg2["glassnote_user_plan"] = server_plan
                    config.save_config(cfg2)
                elif r.status_code == 401:
                    self._sig_verify_error.emit(
                        "Session expired. Please sign in again in Settings."
                    )
                    return
                else:
                    server_plan = None
            except Exception:
                server_plan = None

            if server_plan is None:
                server_plan = cfg.get("glassnote_user_plan", "free").strip() or "free"
                print(f"[session] Server unreachable — using saved plan: {server_plan}")

            # Update banner with live quota (UX-2)
            self._sig_plan_update.emit(server_plan, sessions_used, sessions_remaining)

            # Validate model access
            if not pricing.is_model_allowed(server_plan, model_id):
                plan_name = pricing.get_plan(server_plan)["display_name"]
                self._sig_verify_error.emit(
                    f"{model_id} is not available on the {plan_name} plan. "
                    "Select a different model or upgrade your plan."
                )
                return

            plan_data   = pricing.get_plan(server_plan)
            has_api_url = bool(cfg.get("glassnote_api_url", "").strip())
            is_saas     = has_api_url and not plan_data["byok_allowed"]

            if not is_saas:
                # BYOK mode validation
                if not plan_data["byok_allowed"]:
                    self._sig_verify_error.emit(
                        f"BYOK mode requires the BYOK plan "
                        f"({pricing.PLANS['byok']['price_display']}). "
                        "Upgrade in Settings or use a Cloud plan."
                    )
                    return
                if provider == "anthropic" and not cfg.get("anthropic_api_key", "").strip():
                    self._sig_verify_error.emit(
                        "Claude requires an Anthropic API key in BYOK mode. "
                        "Add one in Settings."
                    )
                    return
                if provider == "openai" and not cfg.get("openai_api_key", "").strip():
                    self._sig_verify_error.emit(
                        "OpenAI models require an OpenAI API key in BYOK mode. "
                        "Add one in Settings."
                    )
                    return
                # BYOK — no backend session registration needed
                self._sig_session_ok.emit("")
                return

            # Phase 2: Register session with backend (BUG-2, BUG-7 fix)
            # 402 is caught HERE before the session opens — not silently ignored.
            self._spinner_phase = "Starting session..."
            company = self.company_input.text().strip() if hasattr(self, "company_input") else ""
            ok, session_id, err = manager.register_with_backend(
                company=company,
                model=model_id,
                proxy_url=cfg.get("glassnote_api_url", "").rstrip("/"),
                proxy_token=token,
            )
            if not ok:
                is_quota = err.get("error_code") == "quota_exceeded"
                if err.get("network_error"):
                    # UX-5: graceful degradation
                    self._sig_session_err.emit(
                        "Cannot reach GlassNote servers. "
                        "Check your internet connection and try again.",
                        False,
                    )
                else:
                    self._sig_session_err.emit(
                        err.get("message", "Failed to start session."),
                        is_quota,
                    )
                return
            self._sig_session_ok.emit(session_id)

        threading.Thread(target=_verify_and_register, daemon=True, name="plan-verify").start()

    # ── Signal handlers (always on main thread) ───────────────────────────────

    def _on_plan_update(self, server_plan: str, sessions_used: int, sessions_remaining: int):
        """
        Called on main thread when /api/auth/me returns.
        Updates the plan banner with live quota data (UX-2, UX-4).
        Does NOT start the session — that happens in _on_session_registered.
        """
        self._pending_plan = server_plan
        self._populate_models(sessions_used=sessions_used, sessions_remaining=sessions_remaining)

    def _on_verify_error(self, message: str):
        """
        Called on main thread when plan verification fails fatally.
        BUG-3 fix: single definition (was duplicated).
        BUG-5 fix: always re-enables the start button via _set_loading(False).
        """
        t = self._tok()
        self._set_loading(False)
        self.error_label.setStyleSheet(f"color: {t['danger']}; font-size: 12px;")
        self.error_label.setText(message)

    def _on_session_registered(self, session_id: str):
        """
        Called on main thread when backend session registration succeeds.
        This is the ONLY place session_started is emitted — after backend confirms.
        BUG-6 fix: audio pipeline warm-up happens in app_controller AFTER this signal.
        """
        self._set_loading(False)
        cfg     = self._pending_cfg or config.load_config()
        plan_id = self._pending_plan or cfg.get("glassnote_user_plan", "free")

        plan_data = pricing.get_plan(plan_id)
        config.set("_session_max_duration_minutes", plan_data["session_duration_minutes"])
        config.set("_session_plan", plan_id)
        config.set("selected_provider", self._pending_provider)
        if self._pending_provider == "anthropic":
            config.set("anthropic_model", self._pending_model)
        else:
            config.set("openai_model", self._pending_model)

        # Start local session with pre-validated backend session_id
        manager.start(
            resume_text=self._resume_text,
            job_description=self.jd_input.toPlainText().strip(),
            company=self.company_input.text().strip(),
            extra_prompt=self.extra_input.toPlainText().strip(),
            language=self.lang_combo.currentText(),
            simple_language=self.simple_lang.isChecked(),
            session_id=session_id,
        )
        self.session_started.emit()
        self.close()

    def _on_session_error(self, message: str, is_quota_error: bool):
        """
        Called on main thread when backend session registration fails.
        BUG-2, BUG-7, UX-1 fix: shows the error to the user instead of silently failing.
        BUG-5 fix: re-enables the start button via _set_loading(False).
        """
        t = self._tok()
        self._set_loading(False)
        self.error_label.setStyleSheet(f"color: {t['danger']}; font-size: 12px;")
        if is_quota_error:
            # UX-1: Rich quota-exceeded error with upgrade CTA
            self.error_label.setText(
                f"{message}\n\n"
                "Upgrade at glassnote.ai/dashboard/billing"
            )
        else:
            self.error_label.setText(message)

    # ── Drag ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()
        try:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(
                int(self.winId()), 0x00000011
            )
        except Exception:
            pass

    @staticmethod
    def _get_plan_from_token(token: str) -> str:
        """Extract plan from JWT token without full verification. Returns 'free' on failure."""
        try:
            import base64, json
            parts = token.split(".")
            if len(parts) != 3:
                return "free"
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            return data.get("plan", "free")
        except Exception:
            return "free"