"""
Global hotkey manager using the `keyboard` library.
These hotkeys fire even when another app (browser, Zoom) has focus.
No focus is stolen from the active window.
"""

import keyboard
import threading
from typing import Callable, Dict


# ── Hotkey definitions ─────────────────────────────────────────────────────────
HOTKEYS = {
    "capture":       "ctrl+shift+c",   # Add screenshot to queue
    "solve":         "ctrl+shift+s",   # Solve queued screenshots
    "analyze":       "ctrl+shift+a",   # Instant capture + solve
    "interview":     "ctrl+shift+i",   # Start/stop audio recording
    "clear_queue":   "ctrl+shift+x",   # Clear screenshot queue
    "toggle_overlay":"ctrl+shift+h",   # Show/hide overlay
    "end_session":   "ctrl+shift+q",   # End session
    "prev_history":  "ctrl+shift+[",   # Previous solution
    "next_history":  "ctrl+shift+]",   # Next solution
    "move_up":       "ctrl+shift+up",
    "move_down":     "ctrl+shift+down",
    "move_left":     "ctrl+shift+left",
    "move_right":    "ctrl+shift+right",
}


class HotkeyManager:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._registered = False
        self._lock = threading.Lock()

    def register(self, action: str, callback: Callable):
        """Register a callback for a named action."""
        with self._lock:
            self._handlers[action] = callback

    def start(self):
        """Bind all registered hotkeys. Call once after all handlers are set."""
        with self._lock:
            if self._registered:
                return
            for action, combo in HOTKEYS.items():
                handler = self._handlers.get(action)
                if handler:
                    # Suppress=True prevents the hotkey from reaching the browser
                    try:
                        keyboard.add_hotkey(combo, handler, suppress=True)
                        print(f"[hotkeys] Registered: {combo} → {action}")
                    except Exception as e:
                        print(f"[hotkeys] Failed to register {combo}: {e}")
            self._registered = True

    def stop(self):
        """Unregister all hotkeys."""
        try:
            keyboard.unhook_all_hotkeys()
            self._registered = False
            print("[hotkeys] All hotkeys unregistered")
        except Exception as e:
            print(f"[hotkeys] Failed to unregister: {e}")

    def update_handler(self, action: str, callback: Callable):
        """Update a handler at runtime."""
        with self._lock:
            self._handlers[action] = callback
            combo = HOTKEYS.get(action)
            if combo and self._registered:
                try:
                    keyboard.remove_hotkey(combo)
                    keyboard.add_hotkey(combo, callback, suppress=True)
                except Exception:
                    pass


# Singleton
manager = HotkeyManager()