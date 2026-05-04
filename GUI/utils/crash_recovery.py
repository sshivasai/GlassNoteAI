"""
utils/crash_recovery.py — Session crash recovery dialog.

Shows a dialog when a previous session is detected, allowing the user
to resume or discard it.

Usage:
    from utils.crash_recovery import show_recovery_dialog

    if session_manager.has_recoverable_session():
        show_recovery_dialog(parent, on_resume, on_discard)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from datetime import datetime
import os
from utils.logger import get_logger

logger = get_logger(__name__)


class CrashRecoveryDialog(QDialog):
    """Dialog for session crash recovery."""

    resume_clicked = pyqtSignal()
    discard_clicked = pyqtSignal()

    def __init__(self, session_info: dict, parent=None):
        super().__init__(parent)
        self.session_info = session_info
        self._setup_ui()

    def _setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Session Recovery")
        self.setModal(True)
        self.setMinimumWidth(500)

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("Previous Session Found")
        title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        title.setFont(title_font)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "GlassNote detected an incomplete session.\n"
            "Would you like to resume where you left off?"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Session details box
        details_box = QTextEdit()
        details_box.setReadOnly(True)
        details_box.setMaximumHeight(150)
        details_box.setStyleSheet("""
            QTextEdit {
                background: #f5f5f7;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
        """)

        # Build details text
        details_text = self._build_details_text()
        details_box.setPlainText(details_text)

        layout.addWidget(details_box)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        discard_btn = QPushButton("Discard")
        discard_btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #e0e0e0;
            }
        """)
        discard_btn.clicked.connect(self._on_discard)
        button_layout.addWidget(discard_btn)

        resume_btn = QPushButton("Resume Session")
        resume_btn.setStyleSheet("""
            QPushButton {
                background: #5b8ff9;
                border: none;
                border-radius: 6px;
                color: white;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #4a7cf7;
            }
        """)
        resume_btn.clicked.connect(self._on_resume)
        resume_btn.setDefault(True)
        button_layout.addWidget(resume_btn)

        layout.addLayout(button_layout)

        self.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLabel {
                color: #333;
            }
        """)

    def _build_details_text(self) -> str:
        """Build session details text."""
        lines = []

        company = self.session_info.get("company", "Unknown")
        lines.append(f"Company: {company}")

        started_at = self.session_info.get("started_at", 0)
        if started_at:
            dt = datetime.fromtimestamp(started_at)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"Started: {time_str}")

        model = self.session_info.get("model", "")
        provider = self.session_info.get("provider", "")
        if model and provider:
            lines.append(f"Model: {provider} / {model}")

        history_count = len(self.session_info.get("history", []))
        if history_count > 0:
            lines.append(f"Questions answered: {history_count}")
        else:
            lines.append("No questions answered yet")

        return "\n".join(lines)

    def _on_resume(self):
        """Handle resume button click."""
        logger.info("User chose to resume session")
        self.resume_clicked.emit()
        self.accept()

    def _on_discard(self):
        """Handle discard button click."""
        logger.info("User chose to discard session")
        self.discard_clicked.emit()
        self.reject()


def show_recovery_dialog(
    session_info: dict,
    parent=None,
    on_resume=None,
    on_discard=None
) -> None:
    """
    Show crash recovery dialog.

    Args:
        session_info: Session information dict
        parent: Parent widget
        on_resume: Callback when user clicks resume
        on_discard: Callback when user clicks discard
    """
    dialog = CrashRecoveryDialog(session_info, parent)

    if on_resume:
        dialog.resume_clicked.connect(on_resume)

    if on_discard:
        dialog.discard_clicked.connect(on_discard)

    dialog.exec()
