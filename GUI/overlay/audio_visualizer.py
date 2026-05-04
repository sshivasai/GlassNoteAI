"""
Modern audio visualizer widget with pulse animation.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen


class AudioPulse(QWidget):
    """
    Animated audio pulse indicator with smooth breathing effect.

    States:
    - idle: Slow green pulse
    - listening: Medium blue pulse
    - speaking: Fast orange pulse with larger amplitude
    - processing: Spinning gradient
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._pulse_radius = 0.5  # 0.0 to 1.0
        self._rotation = 0  # 0 to 360
        self._state = "idle"

        # Animation setup
        self._pulse_anim = QPropertyAnimation(self, b"pulseRadius")
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.4)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # Infinite

        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._rotate)
        self._rotation_timer.setInterval(16)  # ~60 FPS

        # Colors
        self._colors = {
            "idle": QColor(52, 211, 153),       # Green
            "listening": QColor(56, 189, 248),  # Blue
            "speaking": QColor(251, 191, 36),   # Amber
            "processing": QColor(168, 85, 247), # Purple
        }

    @pyqtProperty(float)
    def pulseRadius(self):
        return self._pulse_radius

    @pulseRadius.setter
    def pulseRadius(self, value):
        self._pulse_radius = value
        self.update()

    def set_state(self, state: str):
        """Set visualization state: idle, listening, speaking, processing"""
        if state == self._state:
            return

        self._state = state

        if state == "idle":
            self._pulse_anim.setDuration(1800)
            self._pulse_anim.setStartValue(0.5)
            self._pulse_anim.setEndValue(0.85)
            self._pulse_anim.start()
            self._rotation_timer.stop()

        elif state == "listening":
            self._pulse_anim.setDuration(1200)
            self._pulse_anim.setStartValue(0.4)
            self._pulse_anim.setEndValue(1.0)
            self._pulse_anim.start()
            self._rotation_timer.stop()

        elif state == "speaking":
            self._pulse_anim.setDuration(600)
            self._pulse_anim.setStartValue(0.3)
            self._pulse_anim.setEndValue(1.0)
            self._pulse_anim.start()
            self._rotation_timer.stop()

        elif state == "processing":
            self._pulse_anim.stop()
            self._pulse_radius = 0.8
            self._rotation_timer.start()

        self.update()

    def _rotate(self):
        self._rotation = (self._rotation + 3) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2
        max_radius = min(center_x, center_y) - 2

        color = self._colors.get(self._state, self._colors["idle"])

        if self._state == "processing":
            # Spinning gradient for processing state
            painter.setPen(Qt.PenStyle.NoPen)

            # Outer glow
            gradient = QRadialGradient(center_x, center_y, max_radius * 1.2)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 80))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.drawEllipse(
                int(center_x - max_radius * 1.2),
                int(center_y - max_radius * 1.2),
                int(max_radius * 2.4),
                int(max_radius * 2.4)
            )

            # Core with rotation effect
            gradient = QRadialGradient(center_x, center_y, max_radius * 0.6)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 120))
            painter.setBrush(gradient)
            painter.drawEllipse(
                int(center_x - max_radius * 0.6),
                int(center_y - max_radius * 0.6),
                int(max_radius * 1.2),
                int(max_radius * 1.2)
            )

        else:
            # Pulsing circles for other states
            radius = max_radius * self._pulse_radius

            # Outer glow (fades with pulse)
            painter.setPen(Qt.PenStyle.NoPen)
            glow_alpha = int(40 * (1.0 - self._pulse_radius))
            gradient = QRadialGradient(center_x, center_y, radius * 1.8)
            gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), glow_alpha))
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.drawEllipse(
                int(center_x - radius * 1.8),
                int(center_y - radius * 1.8),
                int(radius * 3.6),
                int(radius * 3.6)
            )

            # Middle ring
            ring_alpha = int(120 * self._pulse_radius)
            pen = QPen(QColor(color.red(), color.green(), color.blue(), ring_alpha))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                int(center_x - radius),
                int(center_y - radius),
                int(radius * 2),
                int(radius * 2)
            )

            # Core circle
            painter.setPen(Qt.PenStyle.NoPen)
            gradient = QRadialGradient(center_x, center_y, radius * 0.5)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 180))
            painter.setBrush(gradient)
            painter.drawEllipse(
                int(center_x - radius * 0.5),
                int(center_y - radius * 0.5),
                int(radius),
                int(radius)
            )

        painter.end()

    def stop(self):
        """Stop all animations"""
        self._pulse_anim.stop()
        self._rotation_timer.stop()


class WaveformBars(QWidget):
    """
    Animated waveform bars (alternative to pulse).
    5 vertical bars that animate based on audio level.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 20)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._bars = [0.3, 0.5, 0.8, 0.6, 0.4]  # Heights 0.0-1.0
        self._target_bars = self._bars.copy()
        self._state = "idle"

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_bars)
        self._anim_timer.setInterval(50)
        self._anim_timer.start()

        self._colors = {
            "idle": QColor(52, 211, 153),
            "active": QColor(56, 189, 248),
            "speaking": QColor(251, 191, 36),
        }

    def set_levels(self, levels: list[float]):
        """Set target bar levels (list of 5 floats, 0.0-1.0)"""
        if len(levels) == 5:
            self._target_bars = levels

    def set_state(self, state: str):
        """idle, active, speaking"""
        self._state = state

    def _animate_bars(self):
        """Smoothly interpolate bars toward targets"""
        changed = False
        for i in range(5):
            diff = self._target_bars[i] - self._bars[i]
            if abs(diff) > 0.01:
                self._bars[i] += diff * 0.2  # Smooth interpolation
                changed = True

        if changed:
            self.update()

        # Randomize targets when idle for breathing effect
        if self._state == "idle" and not hasattr(self, '_idle_counter'):
            import random
            self._target_bars = [random.uniform(0.2, 0.6) for _ in range(5)]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = self._colors.get(self._state, self._colors["idle"])

        bar_width = 4
        gap = 2
        total_width = 5 * bar_width + 4 * gap
        start_x = (self.width() - total_width) / 2

        for i, height in enumerate(self._bars):
            x = start_x + i * (bar_width + gap)
            bar_h = self.height() * height
            y = (self.height() - bar_h) / 2

            # Gradient fill
            gradient = QRadialGradient(x + bar_width/2, y + bar_h/2, bar_h)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 120))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(int(x), int(y), bar_width, int(bar_h), 2, 2)

        painter.end()
