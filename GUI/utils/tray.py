"""
System tray integration.

The tray icon is the ONLY visible presence of the app.
No taskbar entry. No Alt+Tab. No window title bars.

Tray icon provides:
  - Right-click menu: New Session, Settings, Quit
  - Tooltip showing session status
  - Click to toggle pill visibility

Note: The tray icon itself IS visible (it's in the system tray corner).
This is intentional — it's the user's escape hatch to control the app.
It looks like any other system tray utility.
"""

import sys
import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QPen, QBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QObject


def _make_tray_icon() -> QIcon:
    """
    Generate a minimal tray icon programmatically.
    Small dark circle with a green dot — no image file needed.
    """
    size = 64
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer dark circle
    painter.setBrush(QBrush(QColor(20, 20, 22)))
    painter.setPen(QPen(QColor(60, 60, 70), 2))
    painter.drawEllipse(4, 4, size - 8, size - 8)

    # Inner accent dot
    painter.setBrush(QBrush(QColor(79, 142, 247)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(size // 2 - 8, size // 2 - 8, 16, 16)

    painter.end()
    return QIcon(px)


class TrayManager(QObject):
    """Manages the system tray icon and its menu."""

    sig_new_session   = pyqtSignal()
    sig_open_settings = pyqtSignal()
    sig_toggle_pill   = pyqtSignal()
    sig_quit          = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon = None
        self._session_active = False

    def setup(self):
        """Create and show the tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("[tray] System tray not available on this platform")
            return

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("GlassNote — No active session")
        self._tray.activated.connect(self._on_tray_activated)

        self._build_menu()
        self._tray.show()
        print("[tray] Tray icon visible")

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #0e0e0f;
                border: 1px solid #2a2a2e;
                border-radius: 8px;
                padding: 4px;
                color: #e8e8e8;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QMenu::item {
                padding: 7px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #1e1e22;
                color: #4f8ef7;
            }
            QMenu::separator {
                height: 1px;
                background: #2a2a2e;
                margin: 4px 8px;
            }
        """)

        self._status_action = menu.addAction("◈  No active session")
        self._status_action.setEnabled(False)
        menu.addSeparator()

        new_session = menu.addAction("▶  New Session")
        new_session.triggered.connect(self.sig_new_session)

        toggle_pill = menu.addAction("◉  Toggle Overlay")
        toggle_pill.triggered.connect(self.sig_toggle_pill)

        settings = menu.addAction("⚙  Settings")
        settings.triggered.connect(self.sig_open_settings)

        menu.addSeparator()

        quit_action = menu.addAction("✕  Quit")
        quit_action.triggered.connect(self.sig_quit)

        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        """
        Handles system tray activation events (like mouse clicks).
        
        Args:
            reason (QSystemTrayIcon.ActivationReason): The reason for activation.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click → toggle pill
            self.sig_toggle_pill.emit()

    def set_session_active(self, active: bool, label: str = ""):
        """
        Updates the tray icon tooltip and menu to reflect the session status.
        
        Args:
            active (bool): True if a session is currently running.
            label (str): Optional context label (e.g. company name) to display.
        """
        self._session_active = active
        if active:
            status = f"◈  Session active{' — ' + label if label else ''}"
            self._tray.setToolTip(f"GlassNote — {label or 'Session active'}")
        else:
            status = "◈  No active session"
            self._tray.setToolTip("GlassNote — No active session")

        if self._status_action:
            self._status_action.setText(status)

    def show_notification(self, title: str, message: str, duration_ms: int = 2000):
        """
        Shows a tray balloon notification.
        
        Args:
            title (str): The notification title.
            message (str): The notification message body.
            duration_ms (int): Duration to display the notification in milliseconds.
        """
        if self._tray:
            self._tray.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information,
                duration_ms
            )

    def hide(self):
        """Hides the system tray icon from the taskbar."""
        if self._tray:
            self._tray.hide()