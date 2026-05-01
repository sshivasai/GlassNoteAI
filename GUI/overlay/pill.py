# overlay/pill.py
"""
Pill UI — Compact floating control bar with integrated ticker strip.
"""

import sys
import os

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QFont, QColor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import window_hide
from overlay.ticker import TranscriptTicker


# ── Colour tokens ──────────────────────────────────────────────────────────────
_C = {
    "bg":            "rgba(9, 11, 16, 0.96)",
    "border":        "rgba(148, 163, 184, 0.16)",
    "divider":       "rgba(148, 163, 184, 0.14)",
    "text_dim":      "#273041",
    "text_muted":    "#738095",
    "text_normal":   "#aab6c8",
    "text_active":   "#f4f7fb",
    "accent":        "#38bdf8",
    "accent_bg":     "rgba(56, 189, 248, 0.12)",
    "accent_border": "rgba(56, 189, 248, 0.34)",
    "green":         "#34d399",
    "green_bg":      "rgba(52, 211, 153, 0.12)",
    "green_border":  "rgba(52, 211, 153, 0.30)",
    "red":           "#fb7185",
    "red_bg":        "rgba(251, 113, 133, 0.12)",
    "amber":         "#fbbf24",
    "timer":         "rgba(244,247,251,0.30)",
    "dot_idle":      "#34d399",
    "dot_busy":      "#fbbf24",
    "close_fg":      "#738095",
    "close_hover":   "#fb7185",
}


# ── Button styles ──────────────────────────────────────────────────────────────

def _btn_style(
    color:  str = _C["text_normal"],
    bg:     str = "transparent",
    border: str = "transparent",
    weight: str = "400",
) -> str:
    return f"""
        QPushButton {{
            background: {bg};
            border: 1px solid {border};
            color: {color};
            font-size: 11px;
            font-weight: {weight};
            font-family: 'Segoe UI', 'Inter', sans-serif;
            padding: 3px 9px;
            border-radius: 10px;
            letter-spacing: 0.15px;
        }}
        QPushButton:hover {{
            background: {_C['accent_bg']};
            border-color: {_C['accent_border']};
            color: {_C['text_active']};
        }}
        QPushButton:pressed {{
            background: rgba(56,189,248,0.22);
        }}
    """


_STYLE_NORMAL  = _btn_style()
_STYLE_ACTIVE  = _btn_style(
    _C["text_active"], _C["accent_bg"], _C["accent_border"], "600"
)
_STYLE_RECORD  = _btn_style(
    _C["red"], _C["red_bg"], "rgba(251,113,133,0.30)", "600"
)
_STYLE_GREEN   = _btn_style(
    _C["green"], _C["green_bg"], _C["green_border"], "600"
)
_STYLE_SOLVING = _btn_style(
    _C["amber"], "rgba(251,191,36,0.12)", "rgba(251,191,36,0.30)", "600"
)

_STYLE_ICON_BTN = f"""
    QPushButton {{
        background: transparent;
        border: 1px solid {_C['border']};
        color: {_C['text_muted']};
        font-size: 13px;
        padding: 2px 5px;
        border-radius: 8px;
    }}
    QPushButton:hover {{
        color: {_C['text_normal']};
        background: {_C['accent_bg']};
        border-color: {_C['accent_border']};
    }}
"""

_STYLE_CLOSE = f"""
    QPushButton {{
        background: rgba(251,113,133,0.08);
        border: 1px solid rgba(251,113,133,0.20);
        color: {_C['close_fg']};
        font-size: 10px;
        font-weight: 700;
        padding: 1px 5px;
        border-radius: 8px;
        min-width: 20px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        color: white;
        background: {_C['close_hover']};
        border-color: {_C['close_hover']};
    }}
"""

_PILL_CSS = f"""
QWidget#pill_root {{
    background: {_C['bg']};
    border: 1px solid {_C['border']};
    border-radius: 22px;
}}
QLabel#timer_lbl {{
    color: {_C['timer']};
    font-size: 10px;
    font-family: 'Consolas', 'JetBrains Mono', monospace;
    letter-spacing: 0.6px;
    padding: 0 1px;
    font-weight: 600;
}}
QLabel#dot_lbl {{
    font-size: 6px;
    padding: 0 1px 0 2px;
}}
QLabel#badge_lbl {{
    background: {_C['accent']};
    color: white;
    font-size: 8px;
    font-weight: 700;
    font-family: 'Segoe UI', sans-serif;
    border-radius: 6px;
    padding: 0px 4px;
    min-width: 12px;
    max-height: 12px;
}}
"""


class _Divider(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1, 14)
        self.setStyleSheet(
            f"background: {_C['divider']}; border-radius: 1px;"
        )


class PillWindow(QWidget):
    sig_capture        = pyqtSignal()
    sig_solve          = pyqtSignal()
    sig_analyze        = pyqtSignal()
    sig_interview      = pyqtSignal()
    sig_toggle_overlay = pyqtSignal()
    sig_open_settings  = pyqtSignal()
    sig_end_session    = pyqtSignal()
    sig_move           = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._queue_count     = 0
        self._recording       = False
        self._solving         = False
        self._overlay_visible = False
        self._interview_mode  = False
        self._session_secs    = 0
        self._drag_pos        = None

        self._session_clock = QTimer(self)
        self._session_clock.timeout.connect(self._tick_session)
        # NOTE: do NOT start here — start_session_clock() is called by
        # app_controller._show_main_ui() so the timer only runs during an
        # active session, not during the setup window.

        self._build_ui()
        self._add_shadow()

    # ── Construction ───────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(_PILL_CSS)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.root = QWidget()
        self.root.setObjectName("pill_root")
        outer.addWidget(self.root)

        row = QHBoxLayout(self.root)
        row.setContentsMargins(12, 4, 8, 4)
        row.setSpacing(4)

        # Status dot + timer ────────────────────────────────────────────────────
        self._dot = QLabel("●")
        self._dot.setObjectName("dot_lbl")
        self._dot.setStyleSheet(f"color: {_C['dot_idle']}; font-size: 6px;")
        row.addWidget(self._dot)

        self._timer_lbl = QLabel("00:00")
        self._timer_lbl.setObjectName("timer_lbl")
        self._timer_lbl.setFixedWidth(36)   # ← fixed: prevents layout reflow when buttons resize
        row.addWidget(self._timer_lbl)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(4)

        # Action buttons ────────────────────────────────────────────────────────
        self._btn_capture = self._make_btn("📸", "Capture", self.sig_capture, width=74)
        row.addWidget(self._btn_capture)

        self._badge = QLabel("0")
        self._badge.setObjectName("badge_lbl")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setVisible(False)
        row.addWidget(self._badge)

        self._btn_solve   = self._make_btn("⚡", "Solve",   self.sig_solve,   width=70)
        self._btn_analyze = self._make_btn("🖥", "Analyze", self.sig_analyze, width=78)
        row.addWidget(self._btn_solve)
        row.addWidget(self._btn_analyze)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(4)

        # Interview ─────────────────────────────────────────────────────────────
        self._btn_interview = self._make_btn("🎙", "Meeting", self.sig_interview, width=88)
        row.addWidget(self._btn_interview)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(4)

        # Overlay toggle ────────────────────────────────────────────────────────
        self._btn_overlay = QPushButton("◎  Answer")
        self._btn_overlay.setStyleSheet(_STYLE_NORMAL)
        self._btn_overlay.setFixedWidth(80)  # ← fixed: prevent layout shift on state change
        self._btn_overlay.setToolTip("Show / hide answer panel  Ctrl+Shift+H")
        self._btn_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_overlay.clicked.connect(self.sig_toggle_overlay)
        row.addWidget(self._btn_overlay)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(2)

        # Settings ──────────────────────────────────────────────────────────────
        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setStyleSheet(_STYLE_ICON_BTN)
        self._btn_settings.setFixedSize(24, 24)
        self._btn_settings.setToolTip("Settings")
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.clicked.connect(self.sig_open_settings)
        row.addWidget(self._btn_settings)

        row.addSpacing(1)

        # Close ─────────────────────────────────────────────────────────────────
        self._btn_close = QPushButton("✕")
        self._btn_close.setStyleSheet(_STYLE_CLOSE)
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.setToolTip("End Session")
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.sig_end_session)
        row.addWidget(self._btn_close)

        # Ticker ────────────────────────────────────────────────────────────────
        self.ticker = TranscriptTicker()
        self.adjustSize()

    def _make_btn(self, icon: str, label: str, signal, width: int = 0) -> QPushButton:
        btn = QPushButton(f"{icon}  {label}")
        btn.setStyleSheet(_STYLE_NORMAL)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(signal)
        if width:
            # Use minimum width instead of fixed to handle DPI scaling better
            btn.setMinimumWidth(width)
            btn.setSizePolicy(btn.sizePolicy().horizontalPolicy(), btn.sizePolicy().verticalPolicy())
        return btn

    def _add_shadow(self):
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        sh.setColor(QColor(0, 0, 0, 150))
        self.root.setGraphicsEffect(sh)

    # ── Ticker positioning ─────────────────────────────────────────────────────

    def _reposition_ticker(self):
        if self.ticker.is_user_positioned():
            drag_offset = self.ticker.get_drag_offset()
            self.ticker.move(drag_offset.x(), drag_offset.y())
            return
        
        pill_pos = self.pos()
        pill_h   = self.root.height()
        pill_w   = self.root.width()
        ticker_w = self.ticker.width()
        x_offset = (pill_w - ticker_w) // 2
        self.ticker.move(pill_pos.x() + x_offset, pill_pos.y() + pill_h + 5)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_connection_status(self, status: str) -> None:
        """
        PERF-6: Show a transient connection status indicator on the dot/timer area.

        Called by app_controller during the STT/LLM warm-up phase so the user
        can see connections are being established instead of seeing a frozen UI.

        Args:
            status: One of "warming" | "ready" | "" (empty = clear)
        """
        if status == "warming":
            self._dot.setStyleSheet(f"color: {_C['amber']}; font-size: 6px;")
            self._timer_lbl.setToolTip("Warming up connections…")
        elif status == "ready":
            self._dot.setStyleSheet(f"color: {_C['dot_idle']}; font-size: 6px;")
            self._timer_lbl.setToolTip("Ready")
            # Auto-clear "ready" tooltip after 3 seconds
            QTimer.singleShot(3000, lambda: self._timer_lbl.setToolTip(""))
        else:
            self._dot.setStyleSheet(f"color: {_C['dot_idle']}; font-size: 6px;")
            self._timer_lbl.setToolTip("")

    def set_queue_count(self, count: int):
        self._queue_count = count
        self._badge.setText(str(count))
        self._badge.setVisible(count > 0)

    def set_recording(self, recording: bool):
        self._recording = recording
        if recording:
            self._btn_interview.setStyleSheet(_STYLE_RECORD)
            self._btn_interview.setText("🔴  Stop")
        else:
            self._btn_interview.setStyleSheet(_STYLE_NORMAL)
            self._btn_interview.setText("🎙  Meeting")

    def set_continuous_mode(self, active: bool):
        self._interview_mode = active
        if active:
            self._btn_interview.setStyleSheet(_STYLE_GREEN)
            self._btn_interview.setText("🎙  Listening")
            self._reposition_ticker()
            self.ticker.show_interview_mode()
        else:
            self._btn_interview.setStyleSheet(_STYLE_NORMAL)
            self._btn_interview.setText("🎙  Meeting")
            self.ticker.set_user_positioned(False)
            self.ticker.hide_interview_mode()

    def set_solving(self, solving: bool, mode: str = "solve"):
        self._solving = solving

        self._dot.setStyleSheet(
            f"color: {_C['dot_busy']}; font-size: 6px;"
            if solving else
            f"color: {_C['dot_idle']}; font-size: 6px;"
        )

        if mode == "interview":
            self._btn_solve.setText("⚡  Solve")
            self._btn_solve.setStyleSheet(_STYLE_NORMAL)
            self._btn_solve.setEnabled(True)
            return

        if solving:
            self._btn_solve.setText("⏳  Solving…")
            self._btn_solve.setStyleSheet(_STYLE_SOLVING)
            self._btn_solve.setEnabled(False)
        else:
            self._btn_solve.setText("⚡  Solve")
            self._btn_solve.setStyleSheet(_STYLE_NORMAL)
            self._btn_solve.setEnabled(True)

    def set_audio_level(self, level: float):
        if self._interview_mode:
            self.ticker.set_audio_bars(int(level * 5))

    def set_transcribing(self, transcribing: bool):
        color = _C["dot_busy"] if transcribing else _C["dot_idle"]
        self._dot.setStyleSheet(f"color: {color}; font-size: 6px;")

    def set_overlay_visible(self, visible: bool):
        self._overlay_visible = visible
        if visible:
            self._btn_overlay.setText("◉  Answer")
            self._btn_overlay.setStyleSheet(_STYLE_ACTIVE)
        else:
            self._btn_overlay.setText("◎  Answer")
            self._btn_overlay.setStyleSheet(_STYLE_NORMAL)

    def set_user_speaking(self, speaking: bool):
        if not self._interview_mode:
            return
        if speaking:
            self.ticker.set_status_user_speaking()
        else:
            self.ticker.set_status_listening()

    def update_ticker_partial(self, text: str):
        if self._interview_mode:
            self.ticker.update_partial(text)

    def update_ticker_silence(self, age: float, threshold: float):
        if self._interview_mode:
            self.ticker.set_silence_progress(age, threshold)

    def commit_ticker_segment(self, text: str):
        if self._interview_mode:
            self.ticker.commit_segment(text)
            self.ticker.set_status_answering()

    def move_by(self, direction: str):
        step  = 20
        delta = {
            "up":    QPoint(0, -step),
            "down":  QPoint(0,  step),
            "left":  QPoint(-step, 0),
            "right": QPoint( step, 0),
        }.get(direction)
        if delta:
            self.move(self.pos() + delta)
            if self._interview_mode:
                self._reposition_ticker()

    # ── Timer ──────────────────────────────────────────────────────────────────

    def start_session_clock(self):
        """Reset counter and start the session timer. Called by app_controller
        when the pill is shown at session start."""
        self._session_secs = 0
        self._timer_lbl.setText("00:00")
        self._session_clock.start(1000)

    def stop_session_clock(self):
        """Stop the session timer and reset the counter. Called by app_controller
        on session end so a subsequent session always starts from 00:00."""
        self._session_clock.stop()
        self._session_secs = 0
        self._timer_lbl.setText("00:00")

    def _tick_session(self):
        self._session_secs += 1
        m, s = divmod(self._session_secs, 60)
        self._timer_lbl.setText(f"{m:02d}:{s:02d}")

    # ── Drag ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            if self._interview_mode and not self.ticker.is_user_positioned():
                self._reposition_ticker()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(100, self._hide_from_capture)

    def _hide_from_capture(self):
        window_hide.make_fully_invisible(self)
