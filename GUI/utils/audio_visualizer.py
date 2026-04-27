"""
utils/audio_visualizer.py — Audio waveform visualization.

Provides visual feedback for audio recording with waveform display.

Usage:
    from utils.audio_visualizer import AudioVisualizer

    visualizer = AudioVisualizer(parent)
    visualizer.update_level(0.7)  # 0.0 to 1.0
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from collections import deque


class AudioVisualizer(QWidget):
    """
    Real-time audio waveform visualizer.

    Displays:
      - Bar graph of audio levels
      - Smooth interpolation
      - Decay animation
    """

    def __init__(self, parent=None, bar_count: int = 20):
        super().__init__(parent)
        self.bar_count = bar_count
        self.levels = deque([0.0] * bar_count, maxlen=bar_count)
        self.setFixedHeight(40)
        self.setMinimumWidth(200)

        # Animation timer
        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self._decay_levels)
        self._decay_timer.setInterval(50)  # 20 FPS

    def update_level(self, level: float):
        """
        Update audio level.

        Args:
            level: Audio level from 0.0 to 1.0
        """
        # Add new level, remove oldest
        self.levels.append(max(0.0, min(1.0, level)))
        self.update()

        # Start decay timer if not running
        if not self._decay_timer.isActive():
            self._decay_timer.start()

    def _decay_levels(self):
        """Gradually decay levels for smooth animation."""
        decayed = False
        for i in range(len(self.levels)):
            if self.levels[i] > 0.0:
                self.levels[i] = max(0.0, self.levels[i] * 0.95)
                decayed = True

        if decayed:
            self.update()
        else:
            self._decay_timer.stop()

    def paintEvent(self, event):
        """Paint the waveform bars."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        bar_width = width / self.bar_count
        padding = 2

        for i, level in enumerate(self.levels):
            x = i * bar_width
            bar_height = height * level

            # Color gradient based on level
            if level > 0.8:
                color = QColor(240, 96, 96)  # Red for high levels
            elif level > 0.5:
                color = QColor(245, 181, 63)  # Amber for medium
            else:
                color = QColor(91, 143, 249)  # Blue for low

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)

            # Draw bar from bottom
            bar_rect = QRect(
                int(x + padding),
                int(height - bar_height),
                int(bar_width - padding * 2),
                int(bar_height)
            )
            painter.drawRoundedRect(bar_rect, 2, 2)

    def clear(self):
        """Clear all levels."""
        self.levels = deque([0.0] * self.bar_count, maxlen=self.bar_count)
        self._decay_timer.stop()
        self.update()


class SimpleAudioMeter(QWidget):
    """
    Simple audio level meter (single bar).

    More lightweight than full waveform visualizer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.setFixedSize(100, 8)

    def update_level(self, level: float):
        """Update meter level."""
        self.level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event):
        """Paint the meter bar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.setBrush(QBrush(QColor(40, 40, 45)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 4, 4)

        # Level bar
        if self.level > 0:
            level_width = int(self.width() * self.level)

            if self.level > 0.8:
                color = QColor(240, 96, 96)
            elif self.level > 0.5:
                color = QColor(245, 181, 63)
            else:
                color = QColor(66, 214, 138)

            painter.setBrush(QBrush(color))
            level_rect = QRect(0, 0, level_width, self.height())
            painter.drawRoundedRect(level_rect, 4, 4)
