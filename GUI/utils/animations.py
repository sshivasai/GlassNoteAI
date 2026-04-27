"""
utils/animations.py — Smooth UI animations for GlassNote.

Provides fade, slide, and other animations for widgets.

Usage:
    from utils.animations import fade_in, fade_out, slide_in

    fade_in(widget, duration=200)
    slide_in(widget, direction="up", duration=300)
"""

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtWidgets import QGraphicsOpacityEffect


def fade_in(widget, duration: int = 200, on_finished=None):
    """
    Fade in a widget.

    Args:
        widget: Widget to animate
        duration: Animation duration in ms
        on_finished: Optional callback when done
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity")
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    if on_finished:
        animation.finished.connect(on_finished)

    widget.show()
    animation.start()

    # Keep reference to prevent garbage collection
    widget._fade_animation = animation


def fade_out(widget, duration: int = 200, on_finished=None, hide_after: bool = True):
    """
    Fade out a widget.

    Args:
        widget: Widget to animate
        duration: Animation duration in ms
        on_finished: Optional callback when done
        hide_after: Hide widget after fade completes
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity")
    animation.setDuration(duration)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.InCubic)

    def on_complete():
        if hide_after:
            widget.hide()
        if on_finished:
            on_finished()

    animation.finished.connect(on_complete)
    animation.start()

    widget._fade_animation = animation


def slide_in(widget, direction: str = "up", duration: int = 300, distance: int = 50):
    """
    Slide in a widget from a direction.

    Args:
        widget: Widget to animate
        direction: Direction (up, down, left, right)
        duration: Animation duration in ms
        distance: Slide distance in pixels
    """
    start_pos = widget.pos()

    if direction == "up":
        offset = QPoint(0, distance)
    elif direction == "down":
        offset = QPoint(0, -distance)
    elif direction == "left":
        offset = QPoint(distance, 0)
    else:  # right
        offset = QPoint(-distance, 0)

    widget.move(start_pos + offset)

    animation = QPropertyAnimation(widget, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(start_pos + offset)
    animation.setEndValue(start_pos)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    widget.show()
    animation.start()

    widget._slide_animation = animation


def slide_out(widget, direction: str = "down", duration: int = 300, distance: int = 50, hide_after: bool = True):
    """
    Slide out a widget in a direction.

    Args:
        widget: Widget to animate
        direction: Direction (up, down, left, right)
        duration: Animation duration in ms
        distance: Slide distance in pixels
        hide_after: Hide widget after slide completes
    """
    start_pos = widget.pos()

    if direction == "up":
        offset = QPoint(0, -distance)
    elif direction == "down":
        offset = QPoint(0, distance)
    elif direction == "left":
        offset = QPoint(-distance, 0)
    else:  # right
        offset = QPoint(distance, 0)

    animation = QPropertyAnimation(widget, b"pos")
    animation.setDuration(duration)
    animation.setStartValue(start_pos)
    animation.setEndValue(start_pos + offset)
    animation.setEasingCurve(QEasingCurve.Type.InCubic)

    if hide_after:
        animation.finished.connect(widget.hide)

    animation.start()

    widget._slide_animation = animation
