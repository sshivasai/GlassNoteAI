import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Process hiding — must happen before anything else ──────────────────────────
from utils.process_hide import apply_all as _hide_process
_hide_process()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from app_controller import AppController
from utils.tray import TrayManager


def main():
    """
    Entry point for the GlassNote application.
    
    This function initializes the PyQt6 application, sets up high-DPI scaling,
    disguises the process name, and wires up the main application controller
    and system tray manager. It also keeps the application running in the
    background even if no windows are actively displayed.
    """
    # High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Windows Audio Endpoint Builder")  # disguised name
    app.setQuitOnLastWindowClosed(False)   # stay alive when all windows hidden

    # ── Pricing config — fetch from backend in background ──────────────────────
    # Must happen after QApplication is created (so threads can be started) and
    # after config is loaded (so we have the API URL).  The background fetch
    # completes in ~200 ms; by the time the user reaches page 2 of session setup
    # the live pricing data is already in memory.
    try:
        from settings import config as _cfg
        from api.pricing_client import initialise as _init_pricing
        _api_url = _cfg.get("glassnote_api_url", "").strip()
        _init_pricing(api_url=_api_url, background=True)
        print(f"[main] Pricing config fetch scheduled (api_url={_api_url or 'none'})")
    except Exception as _e:
        print(f"[main] Pricing init failed (non-fatal): {_e}")

    # ── System tray ────────────────────────────────────────────
    tray = TrayManager()
    tray.setup()

    # ── App controller ─────────────────────────────────────────
    controller = AppController(app)

    # ── Wire tray → controller ─────────────────────────────────
    tray.sig_new_session.connect(controller._open_session_setup)
    tray.sig_open_settings.connect(controller._on_open_settings)
    tray.sig_toggle_pill.connect(controller._on_toggle_pill)
    tray.sig_quit.connect(lambda: _graceful_quit(app, controller, tray))

    # ── Wire controller → tray status ─────────────────────────
    controller.session_status_changed.connect(tray.set_session_active)

    # ── Launch ─────────────────────────────────────────────────
    controller.launch()
    tray.show_notification(
        "GlassNote",
        "Running in background. Right-click tray icon to start a session.",
        duration_ms=3000,
    )

    sys.exit(app.exec())


def _graceful_quit(app, controller, tray):
    """
    Cleanly shuts down the application and stops all active background threads.

    Delegates to controller._on_end_session(relaunch=False) so that the
    usage_reporter thread is spun up to send the session JSON to the backend
    before the process exits — whether the user quits from the tray menu or
    via task manager.

    Args:
        app (QApplication): The main PyQt6 application instance.
        controller (AppController): The main application coordinator.
        tray (TrayManager): The system tray manager instance.
    """
    print("[main] Graceful shutdown...")
    try:
        controller._on_end_session(relaunch=False)
    except Exception as e:
        print(f"[main] Cleanup error: {e}")
    tray.hide()
    app.quit()


if __name__ == "__main__":
    main()