"""
Transcript Ticker — compact horizontal STT display strip.

Streaming fix
-------------
_word_queue + _stream_timer (60 ms/word).
update_partial() diffs → queues new words → starts drain timer.
commit_segment() flushes queue instantly.
"""

import sys
import os
import collections

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QFontMetrics,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import window_hide


# ── Design tokens ──────────────────────────────────────────────────────────────
_T = {
    "bg":             "rgba(10, 10, 13, 0.96)",
    "border":         "rgba(255,255,255,0.06)",
    "text_partial":   "#b0bcd8",
    "text_committed": "#4f8ef7",
    "text_status":    "#4cca7e",
    "dot_sep":        "#252530",
    "success":        "#4cca7e",
    "accent":         "#4f8ef7",
    "amber":          "#f0a832",
    "red":            "#e05f5f",
    "silence_low":    "#f0a832",
    "silence_mid":    "#4f8ef7",
    "silence_high":   "#4cca7e",
}

_SCROLL_CSS = """
    QScrollArea { background: transparent; border: none; }
    QScrollBar:horizontal { height: 0px; }
    QScrollBar:vertical   { width:  0px; }
"""

MAX_SEGMENTS       = 12
_WORD_INTERVAL_MS  = 60


# ── Ticker content ─────────────────────────────────────────────────────────────

class _TickerContent(QWidget):
    CONTENT_H = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(6, 0, 12, 0)
        self._row.setSpacing(0)
        self.setFixedHeight(self.CONTENT_H)

    def _refresh_width(self):
        w = self._row.sizeHint().width() + 20
        self.setFixedWidth(max(w, 32))

    def _make_lbl(self, text: str, color: str, bold: bool = False,
                  font_size: int = 10) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(
            "Segoe UI", font_size,
            QFont.Weight.Bold if bold else QFont.Weight.Normal,
        ))
        lbl.setStyleSheet(
            f"color:{color}; background:transparent; border:none; "
            f"padding:0 3px; white-space:nowrap;"
        )
        lbl.setFixedHeight(self.CONTENT_H)
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lbl.adjustSize()
        return lbl

    def _add_widget(self, w: QWidget):
        self._row.addWidget(w)
        self._refresh_width()

    def clear_all(self):
        while self._row.count():
            item = self._row.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        self.setFixedWidth(32)

    def add_segment(self, text: str, color: str, bold: bool = False) -> QLabel:
        lbl = self._make_lbl(text, color, bold=bold)
        self._add_widget(lbl)
        return lbl

    def add_dot(self):
        dot = self._make_lbl("·", _T["dot_sep"], font_size=12)
        dot.setFixedWidth(10)
        self._row.addWidget(dot)
        self._refresh_width()

    def add_check(self):
        chk = self._make_lbl("✓", _T["success"], bold=True, font_size=9)
        chk.setFixedWidth(14)
        self._row.addWidget(chk)
        self._refresh_width()

    def update_label_text(self, lbl: QLabel, text: str):
        lbl.setText(text)
        lbl.adjustSize()
        self._refresh_width()

    def widget_count(self) -> int:
        return self._row.count()

    def remove_first_n_widgets(self, n: int):
        for _ in range(min(n, self._row.count())):
            item = self._row.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        self._refresh_width()


# ── Status badge ───────────────────────────────────────────────────────────────

class _StatusBadge(QWidget):
    W_COMPACT = 26
    W_WIDE    = 100
    H         = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.W_COMPACT, self.H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(3)

        self._icon_lbl = QLabel("🎙")
        self._icon_lbl.setFont(QFont("Segoe UI", 11))
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._icon_lbl)

        self._text_lbl = QLabel("")
        self._text_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self._text_lbl.setStyleSheet(
            f"background:transparent; border:none; "
            f"color:{_T['text_status']}; white-space:nowrap;"
        )
        self._text_lbl.setVisible(False)
        lay.addWidget(self._text_lbl)

    def set_state(self, icon: str, label: str, color: str):
        self._icon_lbl.setFont(QFont("Segoe UI", 11))
        self._icon_lbl.setStyleSheet("background:transparent; border:none;")
        self._icon_lbl.setText(icon)

        if label:
            self._text_lbl.setText(label)
            self._text_lbl.setStyleSheet(
                f"background:transparent; border:none; "
                f"color:{color}; white-space:nowrap;"
            )
            self._text_lbl.setVisible(True)
            fm     = QFontMetrics(self._text_lbl.font())
            needed = fm.horizontalAdvance(label) + 28
            self.setFixedWidth(min(needed, self.W_WIDE))
        else:
            self._text_lbl.setVisible(False)
            self.setFixedWidth(self.W_COMPACT)

    def set_audio_bars(self, bars: int):
        filled = "▮" * bars
        empty  = "▯" * (5 - bars)
        self._icon_lbl.setText(filled + empty)
        self._icon_lbl.setFont(QFont("Consolas", 8))
        self._icon_lbl.setStyleSheet(
            f"background:transparent; border:none; color:{_T['text_status']};"
        )


# ── Main ticker window ─────────────────────────────────────────────────────────

class TranscriptTicker(QWidget):
    """
    Compact horizontal scrolling transcript strip.

    Word streaming: _word_queue drained at 60 ms/word.
    Segment pruning: MAX_SEGMENTS = 12.
    """

    BAR_H   = 2
    TOTAL_H = 38

    def __init__(self, parent=None):
        super().__init__(parent)

        self._silence_progress  = 0.0
        self._auto_scroll       = True
        self._user_interacting  = False
        self._drag_start: QPoint | None = None
        self._drag_scroll_start = 0
        self._segments: list[str] = []
        self._partial_lbl: QLabel | None = None
        self._drag_offset: QPoint = QPoint(0, 0)
        self._user_positioned: bool = False

        self._displayed_partial: str               = ""
        self._word_queue: collections.deque[str]   = collections.deque()

        self._build_ui()
        self._add_shadow()

        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(40)
        self._scroll_timer.timeout.connect(self._auto_scroll_tick)

        self._resume_timer = QTimer(self)
        self._resume_timer.setSingleShot(True)
        self._resume_timer.timeout.connect(self._resume_auto_scroll)

        self._stream_timer = QTimer(self)
        self._stream_timer.setInterval(_WORD_INTERVAL_MS)
        self._stream_timer.timeout.connect(self._stream_next_word)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(self.TOTAL_H)
        self.setMinimumWidth(260)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._root = QWidget()
        self._root.setObjectName("ticker_root")
        self._root.setStyleSheet(f"""
            QWidget#ticker_root {{
                background: {_T['bg']};
                border: 1px solid {_T['border']};
                border-radius: 16px;
            }}
        """)
        outer.addWidget(self._root)

        root_row = QHBoxLayout(self._root)
        root_row.setContentsMargins(3, 3, 8, 3)
        root_row.setSpacing(0)

        self._badge = _StatusBadge()
        root_row.addWidget(self._badge)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet(
            f"background: {_T['border']}; border:none; margin: 6px 0;"
        )
        root_row.addWidget(div)
        root_row.addSpacing(3)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(_SCROLL_CSS)
        self._scroll.setFixedHeight(28)
        root_row.addWidget(self._scroll, 1)

        self._content = _TickerContent()
        self._scroll.setWidget(self._content)

    def _add_shadow(self):
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(18)
        sh.setOffset(0, 2)
        sh.setColor(QColor(0, 0, 0, 110))
        self._root.setGraphicsEffect(sh)

    # ── Paint (silence bar) ────────────────────────────────────────────────────

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._silence_progress <= 0.01:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_total_w = self.width() - 20
        bar_x       = 10
        bar_y       = self.TOTAL_H - self.BAR_H - 1
        bar_w       = int(bar_total_w * self._silence_progress)

        if self._silence_progress < 0.60:
            color = QColor(_T["silence_low"])
        elif self._silence_progress < 0.88:
            color = QColor(_T["silence_mid"])
        else:
            color = QColor(_T["silence_high"])

        color.setAlpha(180)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)

        path = QPainterPath()
        path.addRoundedRect(bar_x, bar_y, max(bar_w, 3), self.BAR_H, 1.0, 1.0)
        p.drawPath(path)
        p.end()

    # ── Public API ─────────────────────────────────────────────────────────────

    def show_interview_mode(self):
        self._reset_state()
        self._badge.set_state("🎙", "", _T["text_status"])
        self._scroll_timer.start()
        self.show()
        QTimer.singleShot(120, self._hide_from_capture)

    def hide_interview_mode(self):
        self._scroll_timer.stop()
        self._stream_timer.stop()
        self._silence_progress = 0.0
        self.update()
        self.hide()

    def update_partial(self, text: str):
        text = text.strip()
        if not text:
            return
        old_words = self._displayed_partial.split()
        new_words = text.split()
        if len(new_words) > len(old_words):
            self._word_queue.extend(new_words[len(old_words):])
            if not self._stream_timer.isActive():
                self._stream_timer.start()

    def commit_segment(self, final_text: str):
        self._flush_word_queue()

        if self._partial_lbl is not None:
            self._partial_lbl.setStyleSheet(
                f"color:{_T['text_committed']}; background:transparent; "
                f"border:none; padding:0 3px; white-space:nowrap;"
            )
            self._partial_lbl = None

        self._segments.append(final_text)
        self._displayed_partial = ""

        self._content.add_check()
        self._content.add_dot()
        self._scroll_to_end()

        if len(self._segments) > MAX_SEGMENTS:
            self._prune_segments()

    # ── Word streaming ─────────────────────────────────────────────────────────

    def _stream_next_word(self):
        if not self._word_queue:
            self._stream_timer.stop()
            return
        word = self._word_queue.popleft()
        self._displayed_partial = (
            (self._displayed_partial + " " + word).strip()
        )
        self._show_partial(self._displayed_partial)

    def _flush_word_queue(self):
        if not self._word_queue:
            return
        self._stream_timer.stop()
        remaining = " ".join(self._word_queue)
        self._word_queue.clear()
        self._displayed_partial = (
            (self._displayed_partial + " " + remaining).strip()
        )
        self._show_partial(self._displayed_partial)

    def _show_partial(self, text: str):
        if self._partial_lbl is None:
            if self._segments:
                self._content.add_dot()
            self._partial_lbl = self._content.add_segment(
                text, _T["text_partial"]
            )
        else:
            self._content.update_label_text(self._partial_lbl, text)
        self._scroll_to_end()

    # ── Segment pruning ────────────────────────────────────────────────────────

    def _prune_segments(self):
        keep = self._segments[-(MAX_SEGMENTS // 2):]
        self._content.clear_all()
        self._partial_lbl = None
        for seg in keep:
            self._content.add_segment(seg, _T["text_committed"])
            self._content.add_check()
            self._content.add_dot()
        self._segments = keep
        self._scroll_to_end()

    # ── Status helpers ─────────────────────────────────────────────────────────

    def set_status_listening(self):
        self._badge.set_state("🎙", "", _T["text_status"])

    def set_status_user_speaking(self):
        self._badge.set_state("🎤", "", _T["text_status"])

    def set_status_answering(self):
        self._badge.set_state("⚡", "", _T["accent"])

    def set_status_cooldown(self, remaining: float):
        self._badge.set_state("⏱", f"{remaining:.0f}s", _T["amber"])

    def set_silence_progress(self, age: float, threshold: float):
        self._silence_progress = min(age / max(threshold, 0.1), 1.0)
        self.update()

    def set_audio_bars(self, bars: int):
        self._badge.set_audio_bars(bars)

    def clear_all(self):
        self._reset_state()
        self._silence_progress = 0.0
        self.update()

    def get_drag_offset(self) -> QPoint:
        return self._drag_offset

    def is_user_positioned(self) -> bool:
        return self._user_positioned

    def set_user_positioned(self, positioned: bool):
        self._user_positioned = positioned

    # ── Internal reset ─────────────────────────────────────────────────────────

    def _reset_state(self):
        self._stream_timer.stop()
        self._word_queue.clear()
        self._content.clear_all()
        self._segments.clear()
        self._partial_lbl       = None
        self._displayed_partial = ""
        self._silence_progress  = 0.0

    # ── Scroll ─────────────────────────────────────────────────────────────────

    def _scroll_to_end(self):
        if self._auto_scroll and not self._user_interacting:
            sb = self._scroll.horizontalScrollBar()
            sb.setValue(sb.maximum())

    def _auto_scroll_tick(self):
        if self._user_interacting or not self._auto_scroll:
            return
        sb  = self._scroll.horizontalScrollBar()
        cur = sb.value()
        mx  = sb.maximum()
        if cur < mx:
            sb.setValue(min(cur + 6, mx))

    def _resume_auto_scroll(self):
        self._user_interacting = False
        self._auto_scroll      = True

    # ── Mouse ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._window_drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            self._drag_scroll_start = self._scroll.horizontalScrollBar().value()
            self._user_interacting  = True
            self._auto_scroll       = False
            self._resume_timer.stop()

    def mouseMoveEvent(self, e):
        if self._window_drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._window_drag_pos)
        elif self._drag_start and e.buttons() == Qt.MouseButton.LeftButton:
            delta   = self._drag_start.x() - e.globalPosition().toPoint().x()
            new_val = self._drag_scroll_start + delta
            sb      = self._scroll.horizontalScrollBar()
            sb.setValue(max(0, min(new_val, sb.maximum())))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._window_drag_pos = None
            self._drag_start = None
            self._drag_offset = QPoint(self.x(), self.y())
            self._user_positioned = True
            self._resume_timer.start(3_000)

    def wheelEvent(self, e):
        sb    = self._scroll.horizontalScrollBar()
        delta = -e.angleDelta().y() // 3
        sb.setValue(sb.value() + delta)
        self._user_interacting = True
        self._auto_scroll      = False
        self._resume_timer.start(3_000)

    # ── Show / hide ────────────────────────────────────────────────────────────

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(120, self._hide_from_capture)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._stream_timer.stop()

    def _hide_from_capture(self):
        window_hide.make_fully_invisible(self)