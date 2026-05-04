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
from overlay.audio_visualizer import AudioPulse


# ── Modern Design Tokens ──────────────────────────────────────────────────────
_C = {
    # Base colors - Glass morphism with deeper contrast
    "bg":            "rgba(10, 12, 20, 0.92)",
    "bg_hover":      "rgba(15, 18, 28, 0.95)",
    "border":        "rgba(148, 163, 184, 0.12)",
    "border_hover":  "rgba(148, 163, 184, 0.28)",
    "divider":       "rgba(148, 163, 184, 0.10)",

    # Typography
    "text_dim":      "#3d4658",
    "text_muted":    "#7b8aa3",
    "text_normal":   "#b4c1d8",
    "text_active":   "#f0f4fa",

    # Accent colors - Vibrant cyan/blue
    "accent":        "#22d3ee",
    "accent_bright": "#06b6d4",
    "accent_bg":     "rgba(34, 211, 238, 0.15)",
    "accent_border": "rgba(34, 211, 238, 0.40)",
    "accent_glow":   "rgba(34, 211, 238, 0.25)",

    # Success green
    "green":         "#10b981",
    "green_bright":  "#34d399",
    "green_bg":      "rgba(16, 185, 129, 0.15)",
    "green_border":  "rgba(16, 185, 129, 0.35)",
    "green_glow":    "rgba(16, 185, 129, 0.30)",

    # Warning/active amber
    "amber":         "#f59e0b",
    "amber_bright":  "#fbbf24",
    "amber_bg":      "rgba(245, 158, 11, 0.15)",
    "amber_border":  "rgba(245, 158, 11, 0.35)",

    # Error/close red
    "red":           "#ef4444",
    "red_bright":    "#f87171",
    "red_bg":        "rgba(239, 68, 68, 0.15)",
    "red_border":    "rgba(239, 68, 68, 0.35)",

    # Purple for processing
    "purple":        "#a855f7",
    "purple_bg":     "rgba(168, 85, 247, 0.15)",
    "purple_border": "rgba(168, 85, 247, 0.35)",

    # UI elements
    "timer":         "rgba(244,247,251,0.40)",
    "dot_idle":      "#10b981",
    "dot_busy":      "#f59e0b",
    "close_fg":      "#7b8aa3",
    "close_hover":   "#ef4444",
}


# ── Button styles ──────────────────────────────────────────────────────────────

def _btn_style(
    color:  str = _C["text_normal"],
    bg:     str = "transparent",
    border: str = "transparent",
    weight: str = "500",
    hover_bg: str = None,
    hover_border: str = None,
) -> str:
    hover_bg = hover_bg or _C['accent_bg']
    hover_border = hover_border or _C['accent_border']

    return f"""
        QPushButton {{
            background: {bg};
            border: 1px solid {border};
            color: {color};
            font-size: 11px;
            font-weight: {weight};
            font-family: 'Segoe UI', 'SF Pro Display', 'Inter', sans-serif;
            padding: 4px 10px;
            border-radius: 11px;
            letter-spacing: 0.2px;
        }}
        QPushButton:hover {{
            background: {hover_bg};
            border-color: {hover_border};
            color: {_C['text_active']};
        }}
        QPushButton:pressed {{
            background: {_C['accent_glow']};
        }}
    """


_STYLE_NORMAL  = _btn_style()
_STYLE_ACTIVE  = _btn_style(
    _C["accent"], _C["accent_bg"], _C["accent_border"], "600",
    hover_bg=_C["accent_glow"], hover_border=_C["accent"]
)
_STYLE_RECORD  = _btn_style(
    _C["red_bright"], _C["red_bg"], _C["red_border"], "600",
    hover_bg="rgba(239, 68, 68, 0.25)", hover_border=_C["red"]
)
_STYLE_GREEN   = _btn_style(
    _C["green_bright"], _C["green_bg"], _C["green_border"], "600",
    hover_bg=_C["green_glow"], hover_border=_C["green"]
)
_STYLE_SOLVING = _btn_style(
    _C["amber_bright"], _C["amber_bg"], _C["amber_border"], "600",
    hover_bg="rgba(245, 158, 11, 0.25)", hover_border=_C["amber"]
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
    border: 1.5px solid {_C['border']};
    border-radius: 24px;
}}
QLabel#timer_lbl {{
    color: {_C['timer']};
    font-size: 11px;
    font-family: 'Consolas', 'SF Mono', 'JetBrains Mono', monospace;
    letter-spacing: 0.8px;
    padding: 0 2px;
    font-weight: 600;
}}
QLabel#dot_lbl {{
    font-size: 6px;
    padding: 0 1px 0 2px;
}}
QLabel#badge_lbl {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {_C['accent']},
                                stop:1 {_C['accent_bright']});
    color: white;
    font-size: 9px;
    font-weight: 700;
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
    border-radius: 7px;
    padding: 0px 5px;
    min-width: 14px;
    max-height: 14px;
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
    sig_debug          = pyqtSignal()
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
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        # Modern audio pulse visualizer + timer ─────────────────────────────────
        self._audio_pulse = AudioPulse()
        self._audio_pulse.set_state("idle")
        row.addWidget(self._audio_pulse)

        row.addSpacing(2)

        self._timer_lbl = QLabel("00:00")
        self._timer_lbl.setObjectName("timer_lbl")
        self._timer_lbl.setFixedWidth(40)   # Slightly wider for better spacing
        row.addWidget(self._timer_lbl)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(4)

        # Action buttons ────────────────────────────────────────────────────────
        self._btn_capture = self._make_btn("📸", "Capture", self.sig_capture, width=80)
        row.addWidget(self._btn_capture)

        self._badge = QLabel("0")
        self._badge.setObjectName("badge_lbl")
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setFixedSize(18, 18)  # Fixed size prevents layout shift
        self._badge.setVisible(False)
        row.addWidget(self._badge)

        # Fixed width to accommodate "Solve" and "Solving…"
        self._btn_solve   = self._make_btn("⚡", "Solve",   self.sig_solve,   width=85)
        self._btn_analyze = self._make_btn("🖥", "Analyze", self.sig_analyze, width=85)
        self._btn_debug   = self._make_btn("🐛", "Debug",   self.sig_debug,   width=85)
        row.addWidget(self._btn_solve)
        row.addWidget(self._btn_analyze)
        row.addWidget(self._btn_debug)

        row.addSpacing(4)
        row.addWidget(_Divider())
        row.addSpacing(4)

        # Interview ─────────────────────────────────────────────────────────────
        # Fixed width to accommodate all states: "Meeting" / "Listening" / "Stop"
        self._btn_interview = self._make_btn("🎙", "Meeting", self.sig_interview, width=95)
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
            # Use FIXED width to prevent layout reflow when text changes
            btn.setFixedWidth(width)
        return btn

    def _add_shadow(self):
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(32)
        sh.setOffset(0, 8)
        sh.setColor(QColor(0, 0, 0, 180))
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
            self._audio_pulse.set_state("processing")
            self._timer_lbl.setToolTip("Warming up connections…")
        elif status == "ready":
            self._audio_pulse.set_state("idle")
            self._timer_lbl.setToolTip("Ready")
            # Auto-clear "ready" tooltip after 3 seconds
            QTimer.singleShot(3000, lambda: self._timer_lbl.setToolTip(""))
        else:
            self._audio_pulse.set_state("idle")
            self._timer_lbl.setToolTip("")

    def set_queue_count(self, count: int):
        """Update queue count badge with smooth fade animation."""
        if self._queue_count == count:
            return  # No change, skip update

        self._queue_count = count

        # Smooth fade transition for badge
        if count > 0:
            if not self._badge.isVisible():
                # Badge appearing - fade in
                self._badge.setText(str(count))
                self._badge.setVisible(True)
                self._badge.setStyleSheet(f"""
                    QLabel {{
                        background: {_C['accent']};
                        color: white;
                        font-size: 8px;
                        font-weight: 700;
                        padding: 1px 5px;
                        border-radius: 7px;
                        min-width: 14px;
                    }}
                """)
            else:
                # Badge updating - just change text
                self._badge.setText(str(count))
        else:
            # Badge disappearing - fade out
            self._badge.setVisible(False)

    def set_recording(self, recording: bool):
        """Update recording state without causing layout reflow."""
        if self._recording == recording:
            return  # No change

        self._recording = recording

        # Block signals during update to prevent multiple redraws
        self._btn_interview.blockSignals(True)

        if recording:
            self._btn_interview.setStyleSheet(_STYLE_RECORD)
            self._btn_interview.setText("🔴  Stop")
        else:
            self._btn_interview.setStyleSheet(_STYLE_NORMAL)
            self._btn_interview.setText("🎙  Meeting")

        self._btn_interview.blockSignals(False)

    def set_continuous_mode(self, active: bool):
        """Update interview mode state without causing layout reflow."""
        if self._interview_mode == active:
            return  # No change

        self._interview_mode = active

        # Block signals during update
        self._btn_interview.blockSignals(True)

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

        self._btn_interview.blockSignals(False)

    def set_solving(self, solving: bool, mode: str = "solve"):
        """Update solving state without causing layout reflow."""
        if self._solving == solving:
            return  # No change

        self._solving = solving

        # Update audio pulse state
        self._audio_pulse.set_state("processing" if solving else "idle")

        # Block signals during button update
        self._btn_solve.blockSignals(True)

        if mode == "interview":
            self._btn_solve.setText("⚡  Solve")
            self._btn_solve.setStyleSheet(_STYLE_NORMAL)
            self._btn_solve.setEnabled(True)
        elif solving:
            self._btn_solve.setText("⏳  Solving…")
            self._btn_solve.setStyleSheet(_STYLE_SOLVING)
            self._btn_solve.setEnabled(False)
        else:
            self._btn_solve.setText("⚡  Solve")
            self._btn_solve.setStyleSheet(_STYLE_NORMAL)
            self._btn_solve.setEnabled(True)

        self._btn_solve.blockSignals(False)

    def set_audio_level(self, level: float):
        if self._interview_mode:
            self.ticker.set_audio_bars(int(level * 5))

    def set_transcribing(self, transcribing: bool):
        self._audio_pulse.set_state("listening" if transcribing else "idle")

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
        # Update both pill and ticker
        self._audio_pulse.set_state("speaking" if speaking else "listening")
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
