"""
Region selector overlay.

Shows a semi-transparent fullscreen overlay.
User clicks and drags to select a capture region.
Region is saved to config and used for all subsequent captures.

Usage:
    selector = RegionSelector()
    selector.region_selected.connect(on_region)
    selector.show()
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush


class RegionSelector(QWidget):
    """
    Fullscreen transparent overlay for region selection.
    Draws a dim overlay with a bright selection rectangle.
    """
    region_selected = pyqtSignal(int, int, int, int)  # x, y, w, h
    cancelled       = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start: QPoint = QPoint()
        self._end:   QPoint = QPoint()
        self._selecting = False
        self._confirmed = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # Cover full primary screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dim the whole screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 140))

        if self._selecting and not self._start.isNull() and not self._end.isNull():
            rect = self._get_rect()

            # Cut out (brighten) the selection area
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Clear
            )
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )

            # Draw selection border
            pen = QPen(QColor(79, 142, 247), 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(79, 142, 247, 30)))
            painter.drawRect(rect)

            # Draw size label
            w, h = rect.width(), rect.height()
            size_text = f"{w} × {h}"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            label_x = rect.x() + 6
            label_y = rect.y() - 8 if rect.y() > 24 else rect.y() + rect.height() + 20
            painter.drawText(label_x, label_y, size_text)

        # Instructions
        painter.setPen(QColor(255, 255, 255, 200))
        painter.setFont(QFont("Segoe UI", 13))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "\n\n  Click and drag to select capture region  ·  ESC to cancel  "
        )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._start = e.position().toPoint()
            self._end   = e.position().toPoint()
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, e):
        if self._selecting:
            self._end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._end = e.position().toPoint()
            self._selecting = False
            rect = self._get_rect()

            # Minimum size check
            if rect.width() < 50 or rect.height() < 50:
                self.update()
                return

            self._confirmed = True
            self.hide()
            self.region_selected.emit(
                rect.x(), rect.y(), rect.width(), rect.height()
            )
            self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
            self.cancelled.emit()
            self.close()

    def _get_rect(self) -> QRect:
        x = min(self._start.x(), self._end.x())
        y = min(self._start.y(), self._end.y())
        w = abs(self._end.x() - self._start.x())
        h = abs(self._end.y() - self._start.y())
        return QRect(x, y, w, h)