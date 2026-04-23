"""
Windows-only utility to hide windows from:
- Screen share (Zoom, Meet, Teams, OBS)
- Screenshots
- Screen recordings
- Taskbar
- Alt+Tab switcher

Uses WDA_EXCLUDEFROMCAPTURE — a legitimate Windows 10/11 API
used by banking apps, DRM software, and privacy tools.
"""

import sys
import ctypes


WDA_NONE                = 0x00000000
WDA_MONITOR             = 0x00000001
WDA_EXCLUDEFROMCAPTURE  = 0x00000011  # Win10 2004+


def apply_to_widget(widget) -> bool:
    """
    Apply all invisibility layers to a PyQt6 widget.
    Must be called AFTER the widget is shown (winId is valid).
    Returns True if successful, False on non-Windows.
    """
    if sys.platform != "win32":
        return False

    try:
        hwnd = int(widget.winId())
        return apply_to_hwnd(hwnd)
    except Exception as e:
        print(f"[window_hide] Failed: {e}")
        return False


def apply_to_hwnd(hwnd: int) -> bool:
    """Apply WDA_EXCLUDEFROMCAPTURE directly to a win32 HWND."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        result = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        return result != 0
    except Exception as e:
        print(f"[window_hide] SetWindowDisplayAffinity failed: {e}")
        return False


def remove_from_taskbar(widget) -> bool:
    """
    Remove a window from taskbar and Alt+Tab switcher.
    Call before show() for best results, or re-hide after show().
    """
    if sys.platform != "win32":
        return False
    try:
        import win32gui
        import win32con
        hwnd = int(widget.winId())
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style = (style | win32con.WS_EX_TOOLWINDOW) & ~win32con.WS_EX_APPWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)
        return True
    except Exception as e:
        print(f"[window_hide] remove_from_taskbar failed: {e}")
        return False


def make_fully_invisible(widget) -> bool:
    """
    Apply ALL invisibility layers to a widget.
    Call this after widget.show().
    """
    r1 = apply_to_widget(widget)
    r2 = remove_from_taskbar(widget)
    return r1 or r2  # at least one succeeded