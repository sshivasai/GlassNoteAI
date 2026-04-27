"""
utils/quota_indicator.py — Rate limit and quota visualization.

Shows usage stats and quota limits in the UI.

Usage:
    from utils.quota_indicator import QuotaIndicator

    indicator = QuotaIndicator(parent)
    indicator.update_usage(used=45, limit=100)
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class QuotaIndicator(QWidget):
    """
    Visual indicator for API quota/rate limits.

    Shows:
      - Current usage vs limit
      - Progress bar with color coding
      - Warning when approaching limit
    """

    quota_exceeded = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._usage = 0
        self._limit = 100
        self._setup_ui()

    def _setup_ui(self):
        """Setup indicator UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Label
        self._label = QLabel("Quota:")
        self._label.setFont(QFont("Segoe UI", 9))
        layout.addWidget(self._label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setValue(0)
        self._progress.setFixedWidth(100)
        self._progress.setFixedHeight(12)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                background: rgba(255, 255, 255, 0.05);
            }
            QProgressBar::chunk {
                border-radius: 5px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #42d68a,
                    stop:1 #5b8ff9
                );
            }
        """)
        layout.addWidget(self._progress)

        # Usage text
        self._usage_label = QLabel("0 / 100")
        self._usage_label.setFont(QFont("Consolas", 8))
        self._usage_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")
        layout.addWidget(self._usage_label)

        self.setMaximumWidth(220)

    def update_usage(self, used: int, limit: int, plan: str = ""):
        """
        Update usage display.

        Args:
            used: Current usage
            limit: Usage limit
            plan: Optional plan name
        """
        self._usage = used
        self._limit = max(limit, 1)  # Avoid division by zero

        # Update progress bar
        percentage = min((used / self._limit) * 100, 100)
        self._progress.setValue(int(percentage))

        # Update text
        self._usage_label.setText(f"{used} / {limit}")

        if plan:
            self._label.setText(f"{plan}:")

        # Color code based on usage
        if percentage >= 100:
            # Exceeded
            self._progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid rgba(240, 96, 96, 0.3);
                    border-radius: 6px;
                    background: rgba(240, 96, 96, 0.1);
                }
                QProgressBar::chunk {
                    border-radius: 5px;
                    background: #f06060;
                }
            """)
            self._usage_label.setStyleSheet("color: #f06060; font-weight: 600;")
            self.quota_exceeded.emit()

        elif percentage >= 80:
            # Warning
            self._progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid rgba(245, 181, 63, 0.3);
                    border-radius: 6px;
                    background: rgba(245, 181, 63, 0.1);
                }
                QProgressBar::chunk {
                    border-radius: 5px;
                    background: #f5b53f;
                }
            """)
            self._usage_label.setStyleSheet("color: #f5b53f; font-weight: 600;")

        else:
            # Normal
            self._progress.setStyleSheet("""
                QProgressBar {
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 6px;
                    background: rgba(255, 255, 255, 0.05);
                }
                QProgressBar::chunk {
                    border-radius: 5px;
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #42d68a,
                        stop:1 #5b8ff9
                    );
                }
            """)
            self._usage_label.setStyleSheet("color: rgba(255, 255, 255, 0.6);")

    def get_usage_percentage(self) -> float:
        """Get current usage as percentage."""
        if self._limit == 0:
            return 0.0
        return (self._usage / self._limit) * 100

    def is_near_limit(self, threshold: float = 0.8) -> bool:
        """Check if usage is near limit."""
        return self.get_usage_percentage() >= (threshold * 100)

    def is_exceeded(self) -> bool:
        """Check if quota is exceeded."""
        return self._usage >= self._limit


# ── Helper Functions ───────────────────────────────────────────────────────────

def format_quota_message(used: int, limit: int, period: str = "monthly") -> str:
    """
    Format quota usage message.

    Args:
        used: Current usage
        limit: Usage limit
        period: Time period (e.g., "monthly", "daily")

    Returns:
        str: Formatted message
    """
    percentage = (used / max(limit, 1)) * 100

    if percentage >= 100:
        return f"⚠️ Quota exceeded: {used}/{limit} {period}"
    elif percentage >= 80:
        remaining = limit - used
        return f"⚠️ Low quota: {remaining} remaining this {period}"
    else:
        return f"Quota: {used}/{limit} {period} ({percentage:.0f}%)"
