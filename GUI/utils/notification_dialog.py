"""
utils/notification_dialog.py

Modal notification dialog for GlassNote.

Shows a single system notification as a proper modal popup with two actions:
  - "Remind Me Later" → closes dialog, notification will reappear next launch
  - "Got it"          → permanently dismisses the notification (saves ID to config)

Styled to match the dark GlassNote UI theme.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


# ── Type → accent colour mapping ─────────────────────────────────────────────
_TYPE_COLOURS = {
    "info":     "#5b8ff9",   # blue
    "warning":  "#f5a623",   # amber
    "critical": "#e05252",   # red
}

_TYPE_ICONS = {
    "info":     "ℹ",
    "warning":  "⚠",
    "critical": "🔴",
}


class NotificationDialog(QDialog):
    """
    Modal dialog that presents a single GlassNote system notification.

    Signals
    -------
    dismissed(str)
        Emitted with the notification ID when the user clicks "Got it".
        The caller should persist this ID to config so the notification
        is never shown again.
    remind_later()
        Emitted when the user clicks "Remind Me Later".
        The caller should NOT persist the ID — the notification will
        reappear on the next app launch.
    """

    dismissed   = pyqtSignal(str)   # notification_id
    remind_later = pyqtSignal()

    def __init__(self, notification: dict, parent=None):
        """
        Parameters
        ----------
        notification : dict
            A NotificationOut dict from the backend, expected keys:
              id      (str)  — UUID
              title   (str)
              message (str)
              type    (str)  — "info" | "warning" | "critical"
        parent : QWidget, optional
        """
        super().__init__(parent)

        self._nid     = notification.get("id", "")
        self._title   = notification.get("title", "GlassNote Notification")
        self._message = notification.get("message", "")
        self._ntype   = notification.get("type", "info")

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        accent = _TYPE_COLOURS.get(self._ntype, _TYPE_COLOURS["info"])
        icon   = _TYPE_ICONS.get(self._ntype, "ℹ")

        # ── Window flags ──────────────────────────────────────────────────────
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedWidth(440)

        # ── Outer container (provides the rounded border) ─────────────────────
        outer = QFrame(self)
        outer.setObjectName("notif_outer")
        outer.setStyleSheet(f"""
            QFrame#notif_outer {{
                background: #111115;
                border: 1px solid #1e1e24;
                border-radius: 12px;
            }}
        """)

        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ── Accent bar at the top ─────────────────────────────────────────────
        accent_bar = QFrame(outer)
        accent_bar.setFixedHeight(4)
        accent_bar.setStyleSheet(f"""
            background: {accent};
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        """)
        outer_layout.addWidget(accent_bar)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QFrame(outer)
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 20)
        body_layout.setSpacing(12)

        # Title row: icon + title text
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.setContentsMargins(0, 0, 0, 0)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"color: {accent}; font-size: 18px; background: transparent;")
        icon_lbl.setFixedWidth(24)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(icon_lbl)

        title_lbl = QLabel(self._title)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.DemiBold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet("color: #e0e0e8; background: transparent;")
        title_lbl.setWordWrap(True)
        title_row.addWidget(title_lbl, 1)

        body_layout.addLayout(title_row)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #1e1e24; background: #1e1e24; border: none; max-height: 1px;")
        body_layout.addWidget(divider)

        # Message
        msg_lbl = QLabel(self._message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #888; font-size: 12px; background: transparent; line-height: 1.5;")
        msg_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        msg_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        body_layout.addWidget(msg_lbl)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 8, 0, 0)

        self._btn_remind = QPushButton("Remind Me Later")
        self._btn_remind.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_remind.setFixedHeight(36)
        self._btn_remind.setStyleSheet("""
            QPushButton {
                background: #252530;
                color: #888;
                border: 1px solid #2e2e3a;
                border-radius: 8px;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: #2e2e3c;
                color: #aaa;
            }
            QPushButton:pressed {
                background: #1e1e28;
            }
        """)
        self._btn_remind.clicked.connect(self._on_remind_later)
        btn_row.addWidget(self._btn_remind)

        self._btn_dismiss = QPushButton("Got it")
        self._btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_dismiss.setFixedHeight(36)
        self._btn_dismiss.setDefault(True)
        self._btn_dismiss.setStyleSheet(f"""
            QPushButton {{
                background: {accent};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {_lighten(accent, 20)};
            }}
            QPushButton:pressed {{
                background: {_darken(accent, 20)};
            }}
        """)
        self._btn_dismiss.clicked.connect(self._on_dismiss)
        btn_row.addWidget(self._btn_dismiss)

        body_layout.addLayout(btn_row)
        outer_layout.addWidget(body)

        # ── Dialog layout ─────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(outer)
        self.setLayout(root)

        # ── Transparent dialog background ─────────────────────────────────────
        self.setStyleSheet("background: transparent;")

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_dismiss(self):
        """User clicked 'Got it' — permanently dismiss this notification."""
        self.dismissed.emit(self._nid)
        self.accept()

    def _on_remind_later(self):
        """User clicked 'Remind Me Later' — close without persisting."""
        self.remind_later.emit()
        self.reject()

    # ── Keyboard shortcut: Enter = Got it, Escape = Remind Me Later ──────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_remind_later()
        else:
            super().keyPressEvent(event)


# ── Colour helpers ────────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str):
    """Convert '#rrggbb' to (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _lighten(hex_color: str, amount: int = 20) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(r + amount, g + amount, b + amount)


def _darken(hex_color: str, amount: int = 20) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return _rgb_to_hex(r - amount, g - amount, b - amount)
