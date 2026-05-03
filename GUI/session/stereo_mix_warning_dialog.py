"""
Stereo Mix Warning Dialog

Shows a modal warning when Stereo Mix is not enabled but the user has selected
system audio or both audio sources. Provides instructions and options to proceed.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class StereoMixWarningDialog(QDialog):
    """
    Modal dialog warning user about missing Stereo Mix.

    User can:
    - Open Settings to change audio source
    - Continue anyway (will use mic as fallback)
    - Check "Don't show again" to suppress future warnings
    """
    open_settings_requested = pyqtSignal()

    def __init__(self, warning_message: str, instructions: str, parent=None):
        super().__init__(parent)
        self._warning_message = warning_message
        self._instructions = instructions
        self._user_choice = None
        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        self.setWindowTitle("Stereo Mix Not Available")
        self.setModal(True)
        self.setFixedWidth(600)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Warning icon + title
        header = QHBoxLayout()
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 32px;")
        header.addWidget(icon_label)

        title_label = QLabel("System Audio Capture Unavailable")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        # Warning message
        warning_text = QLabel(self._warning_message)
        warning_text.setWordWrap(True)
        warning_text.setStyleSheet("font-size: 13px; line-height: 1.5;")
        layout.addWidget(warning_text)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #e7edf4;")
        layout.addWidget(sep)

        # Instructions (collapsible/expandable)
        instructions_label = QLabel("How to enable Stereo Mix:")
        instructions_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(instructions_label)

        instructions_text = QTextEdit()
        instructions_text.setReadOnly(True)
        instructions_text.setMarkdown(self._instructions)
        instructions_text.setFixedHeight(280)
        instructions_text.setStyleSheet("""
            QTextEdit {
                background: #f7f9fc;
                border: 1px solid #d8e0ea;
                border-radius: 6px;
                padding: 12px;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(instructions_text)

        # Don't show again checkbox
        self._dont_show_again = QCheckBox("Don't show this warning again")
        self._dont_show_again.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._dont_show_again)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #e7edf4;")
        layout.addWidget(sep2)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self._btn_settings = QPushButton("Open Settings")
        self._btn_settings.setFixedHeight(36)
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.setStyleSheet("""
            QPushButton {
                background: #0284c7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #0369a1;
            }
        """)
        self._btn_settings.clicked.connect(self._on_open_settings)
        button_layout.addWidget(self._btn_settings)

        self._btn_continue = QPushButton("Continue Anyway")
        self._btn_continue.setFixedHeight(36)
        self._btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_continue.setStyleSheet("""
            QPushButton {
                background: #f7f9fc;
                color: #526071;
                border: 1px solid #d8e0ea;
                border-radius: 6px;
                padding: 0 20px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #e7edf4;
                border-color: #ccd6e3;
            }
        """)
        self._btn_continue.clicked.connect(self._on_continue)
        button_layout.addWidget(self._btn_continue)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setFixedHeight(36)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8995a6;
                border: none;
                padding: 0 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #526071;
            }
        """)
        self._btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self._btn_cancel)

        layout.addLayout(button_layout)

        # Apply dark theme if needed
        self._apply_theme()

    def _apply_theme(self):
        """Apply theme based on system settings."""
        # For now, using light theme. Can be extended to support dark theme.
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
            }
            QLabel {
                color: #111827;
            }
        """)

    def _on_open_settings(self):
        """User wants to open Settings to change audio source."""
        self._user_choice = "settings"
        self.open_settings_requested.emit()
        self.reject()

    def _on_continue(self):
        """User wants to continue despite the warning."""
        self._user_choice = "continue"
        self.accept()

    def should_suppress_warning(self) -> bool:
        """Returns True if user checked 'Don't show again'."""
        return self._dont_show_again.isChecked()

    def get_user_choice(self) -> str:
        """
        Returns the user's choice: "settings", "continue", or "cancel".
        """
        return self._user_choice or "cancel"


def show_stereo_mix_warning(
    warning_message: str,
    instructions: str,
    parent=None
) -> tuple[str, bool]:
    """
    Show the Stereo Mix warning dialog and return user's choice.

    Args:
        warning_message: Main warning text
        instructions: How-to instructions for enabling Stereo Mix
        parent: Parent widget

    Returns:
        tuple[str, bool]: (choice, suppress_future_warnings)
            choice: "settings", "continue", or "cancel"
            suppress: True if user checked "Don't show again"
    """
    dialog = StereoMixWarningDialog(warning_message, instructions, parent)
    dialog.exec()
    return (dialog.get_user_choice(), dialog.should_suppress_warning())


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    test_warning = """⚠️ **Stereo Mix Not Enabled**

You've selected **System Audio** as the audio source, but Stereo Mix is not available.

**What this means:**
- Interview mode will fall back to **Microphone**
- Your mic will capture BOTH interviewer (from speakers) and your voice
"""

    test_instructions = """**How to enable Stereo Mix:**

1. Right-click the **speaker icon** in the taskbar
2. Select **Sounds** → go to the **Recording** tab
3. Right-click in the empty space → **Show Disabled Devices**
4. Right-click **Stereo Mix** → **Enable**
5. Click **OK** and restart the application
"""

    choice, suppress = show_stereo_mix_warning(test_warning, test_instructions)
    print(f"User choice: {choice}")
    print(f"Suppress future: {suppress}")

    sys.exit(0)
