# ===== File: app_controller.py (continued — complete file) =====
"""
App Controller — central coordinator.

Changes in this revision
------------------------
- _dispatch_llm(): uses build_interview_prompt_lean() automatically
  when smart_answering=True → saves 100–400 ms TTFT per interview turn
  by reducing system prompt from ~1200 to ~80 tokens.

- _start_continuous_recording(): calls _warm_stt_connection() alongside
  llm_client.warm_connections() so both LLM and STT TCP+TLS handshakes
  complete before the first question arrives.

- _warm_stt_connection(): new private method — lightweight HTTPS GET to
  the STT provider's REST API pre-warms DNS + TCP + TLS for the
  WebSocket that opens milliseconds later.
  Deepgram        → GET api.deepgram.com/v1/models
  OpenAI Realtime → GET api.openai.com/v1/models
  (OpenAI already warmed by LLM warm when selected_provider=openai;
   httpx reuses the existing connection so it costs < 1 ms.)

- prompts.clear_prompt_cache() called on settings save so session
  context changes take effect immediately on the next question.

- llm_client.warm_connections(cfg=cfg) — passes already-loaded config
  dict to avoid a redundant disk read inside warm_connections().
"""

import sys
import os
import time
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from overlay.pill import PillWindow
from overlay.answer import AnswerOverlay
from hotkeys.manager import manager as hotkey_manager
from session.manager import manager as session_manager
from capture.queue import ScreenshotQueue
from capture import screenshot as screencap
from capture.auto_watcher import AutoWatcher
from llm.streamer import streamer as llm_streamer
from llm.client import client as llm_client
from llm import prompts
from audio.pipeline import AudioPipeline
from settings import config
from utils.perf import tracker as perf_tracker


class AppController(QObject):
    """
    Central controller for the GlassNote application.
    Coordinates UI overlays, audio capturing, screenshot capturing, 
    and LLM dispatches via hotkeys and system tray events.
    """
    session_status_changed = pyqtSignal(bool, str)

    _sig_capture        = pyqtSignal()
    _sig_solve          = pyqtSignal()
    _sig_analyze        = pyqtSignal()
    _sig_interview      = pyqtSignal()
    _sig_toggle_overlay = pyqtSignal()
    _sig_end_session    = pyqtSignal()
    _sig_prev_history   = pyqtSignal()
    _sig_next_history   = pyqtSignal()
    _sig_move           = pyqtSignal(str)
    _sig_queue_count    = pyqtSignal(int)
    _sig_audio_level    = pyqtSignal(float)
    _sig_notifications    = pyqtSignal(list)   # thread-safe notification delivery
    _sig_start_pipeline   = pyqtSignal()       # BUG-9/PERF-2: cross-thread pipeline start
    _sig_connection_ready = pyqtSignal()       # PERF-6: warm-up complete → pill dot green

    def __init__(self, app: QApplication):
        """
        Initializes the AppController.
        
        Args:
            app (QApplication): The main PyQt6 application instance.
        """
        super().__init__()
        self.app        = app
        self._recording = False
        self._settings_window = None
        self._session_window  = None
        self._dispatch_start_time = 0.0
        self._dispatch_model      = ""
        self._dispatch_mode       = "solve"
        self._pill_shown: bool    = False

        # PERF-5: Cache /api/auth/me response for session duration.
        # Populated in _on_session_started(), cleared in _on_end_session().
        # Avoids repeated round-trips for plan/quota checks during a session.
        self._cached_user_info: dict = {}

        # ── Session duration enforcement ───────────────────────────────────────
        # _session_end_time: Unix timestamp when the session must auto-end.
        #   0.0 = no limit (unlimited plan).
        # _session_warn_shown: True once the 5-minute warning has been shown
        #   so we don't spam it every 30 s.
        self._session_end_time:   float = 0.0
        self._session_warn_shown: bool  = False

        # Fires every 30 s while a session is active to check remaining time.
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(30_000)   # 30 seconds
        self._session_timer.timeout.connect(self._check_session_duration)

        self._queue = ScreenshotQueue(
            on_count_change=lambda c: self._sig_queue_count.emit(c)
        )
        self._watcher = AutoWatcher(
            on_capture=self._on_auto_capture,
            interval_seconds=config.get("auto_capture_interval", 5),
            diff_threshold=0.10,
        )
        self._audio = AudioPipeline()

        # 100 ms poll — worst-case dispatch delay 99 ms
        self._silence_timer = QTimer(self)
        self._silence_timer.setInterval(100)
        self._silence_timer.timeout.connect(self._check_silence)

        # Notification polling — startup + every hour
        self._notif_timer = QTimer(self)
        self._notif_timer.setInterval(60 * 60 * 1000)  # 1 hour
        self._notif_timer.timeout.connect(self._poll_notifications)

        self._build_windows()
        self._connect_signals()
        self._setup_hotkeys()

        # Poll for notifications immediately after startup (500 ms delay)
        QTimer.singleShot(500, self._poll_notifications)
        # Check for app updates (future scope scaffolding)
        QTimer.singleShot(2000, self._check_for_updates)

        self._notif_timer.start()
        self._sig_notifications.connect(self._show_notifications)


    # ── Build windows ──────────────────────────────────────────────────────────

    def _build_windows(self):
        self.pill    = PillWindow()
        self.overlay = AnswerOverlay()

        screen = self.app.primaryScreen().geometry()
        pill_x = (screen.width() - 420) // 2
        self.pill.move(pill_x, 20)
        self.overlay.move(pill_x - 60, 80)

    # ── Connect signals ────────────────────────────────────────────────────────

    def _connect_signals(self):
        self.pill.sig_capture.connect(self._on_capture)
        self.pill.sig_solve.connect(self._on_solve)
        self.pill.sig_analyze.connect(self._on_analyze)
        self.pill.sig_interview.connect(self._on_interview_toggle)
        self.pill.sig_toggle_overlay.connect(self._on_toggle_overlay)
        self.pill.sig_open_settings.connect(self._on_open_settings)
        self.pill.sig_end_session.connect(self._on_end_session)

        self._sig_capture.connect(self._on_capture)
        self._sig_solve.connect(self._on_solve)
        self._sig_analyze.connect(self._on_analyze)
        self._sig_interview.connect(self._on_interview_toggle)
        self._sig_toggle_overlay.connect(self._on_toggle_overlay)
        self._sig_end_session.connect(self._on_end_session)
        self._sig_prev_history.connect(self.overlay.prev_history)
        self._sig_next_history.connect(self.overlay.next_history)
        self._sig_move.connect(self._on_move)
        self._sig_queue_count.connect(self.pill.set_queue_count)
        self._sig_audio_level.connect(self.pill.set_audio_level)

        self._audio.recording_started.connect(self._on_recording_started)
        self._audio.recording_stopped.connect(self._on_recording_stopped)
        self._audio.partial_transcript.connect(self._on_partial_transcript)
        self._audio.transcript_ready.connect(self._on_transcript_ready)
        self._audio.transcribe_error.connect(self._on_transcribe_error)
        self._audio.level_update.connect(
            lambda lvl: self._sig_audio_level.emit(lvl)
        )
        self._audio.user_speaking_changed.connect(self._on_user_speaking_changed)
        self._audio.stereo_mix_warning.connect(self._on_stereo_mix_warning)
        # BUG-9/PERF-2: cross-thread pipeline warm start after STT credentials pre-fetch
        self._sig_start_pipeline.connect(self._audio.start_recording_with_source)
        # PERF-6: warm-up complete → pill dot turns green
        self._sig_connection_ready.connect(self._on_connection_ready)

    def _on_user_speaking_changed(self, speaking: bool):
        self.pill.set_user_speaking(speaking)

        # Auto-resume pipeline when user stops speaking
        # (only when auto_answer=True AND smart_answering=True)
        if not speaking:
            cfg = config.load_config()
            auto_answer = cfg.get("auto_answer", False)
            smart_answering = cfg.get("smart_answering", True)

            # Only auto-resume if BOTH auto_answer and smart_answering are enabled
            # This ensures the buffered smart dispatch is flushed
            if auto_answer and smart_answering:
                # Resume the pipeline to dispatch any pending smart dispatch
                self._audio.resume()

    def _on_stereo_mix_warning(self):
        """
        Show warning when Stereo Mix is not enabled.

        Windows requires 'Stereo Mix' or similar loopback device to be manually
        enabled in Recording Devices for system audio capture to work.
        """
        warning_msg = (
            "**System Audio Capture Requires 'Stereo Mix'**\n\n"
            "To capture system audio (interviewer's voice), you need to enable "
            "the 'Stereo Mix' recording device in Windows.\n\n"
            "**How to enable:**\n"
            "1. Right-click the **speaker icon** in the taskbar → **Sounds**\n"
            "2. Go to the **Recording** tab\n"
            "3. Right-click in the empty space → **Show Disabled Devices**\n"
            "4. Right-click **Stereo Mix** → **Enable**\n"
            "5. Click **OK** and restart interview mode\n\n"
            "_Currently using microphone as fallback (captures both voices)._"
        )

        # Show non-destructive banner (doesn't overwrite active answer)
        if hasattr(self.overlay, 'show_notification_banner'):
            self.overlay.show_notification_banner(warning_msg, "warning")
        else:
            # Fallback: show as error overlay
            self.overlay.set_error(warning_msg)

        self.overlay.show()
        self.pill.set_overlay_visible(True)

        print("[app] ⚠️  Stereo Mix warning shown to user")

    # ── Hotkeys ────────────────────────────────────────────────────────────────

    def _setup_hotkeys(self):
        hotkey_manager.register("capture",        lambda: self._sig_capture.emit())
        hotkey_manager.register("solve",          lambda: self._sig_solve.emit())
        hotkey_manager.register("analyze",        lambda: self._sig_analyze.emit())
        hotkey_manager.register("interview",      lambda: self._sig_interview.emit())
        hotkey_manager.register("toggle_overlay", lambda: self._sig_toggle_overlay.emit())
        hotkey_manager.register("end_session",    lambda: self._sig_end_session.emit())
        hotkey_manager.register("prev_history",   lambda: self._sig_prev_history.emit())
        hotkey_manager.register("next_history",   lambda: self._sig_next_history.emit())
        hotkey_manager.register("move_up",        lambda: self._sig_move.emit("up"))
        hotkey_manager.register("move_down",      lambda: self._sig_move.emit("down"))
        hotkey_manager.register("move_left",      lambda: self._sig_move.emit("left"))
        hotkey_manager.register("move_right",     lambda: self._sig_move.emit("right"))
        hotkey_manager.start()

    # ── Notifications polling ──────────────────────────────────────────────────

    def _check_for_updates(self):
        """
        Check glassnote.ai for a newer version of the executable.
        If a new version is available, show a system notification or UI prompt
        directing the user to download the latest installer.
        """
        from utils.updater import check_for_updates, get_current_version, open_download_url

        cfg = config.load_config()
        api_url = cfg.get("glassnote_api_url", "").strip()

        if not api_url:
            return  # No API URL configured

        current_ver = get_current_version()

        def on_update_available(update_info):
            """Handle update notification."""
            latest = update_info.get("latest_version", "")
            download_url = update_info.get("download_url", "")
            is_critical = update_info.get("is_critical", False)

            title = "Critical Update!" if is_critical else "Update Available"
            message = (
                f"GlassNote {latest} is available.\n"
                f"You're on {current_ver}.\n\n"
                f"Click to download."
            )

            # Show in overlay if pill is visible
            if self.pill.isVisible():
                self.overlay.set_error(
                    f"**{title}**\n\n{message}\n\n"
                    f"[Download from glassnote.ai]({download_url})"
                )
                self.overlay.show()
                self.pill.set_overlay_visible(True)

            # Also show tray notification
            if hasattr(self, '_tray_manager'):
                self._tray_manager.show_notification(title, message, duration_ms=10000)

            print(f"[app] Update available: {current_ver} → {latest}")

        def on_error(error_msg):
            """Handle update check error."""
            print(f"[app] Update check failed: {error_msg}")

        check_for_updates(
            current_version=current_ver,
            api_url=api_url,
            on_update_available=on_update_available,
            on_error=on_error,
            silent=True,  # Only notify if update is available
        )

    def _poll_notifications(self):
        """
        Poll /api/notifications/active in a background thread.

        Called on startup (after 500 ms) and then every hour.
        Dismissed notification IDs are stored in config so users
        are not re-shown alerts they have already acknowledged.
        """
        cfg         = config.load_config()
        api_url     = cfg.get("glassnote_api_url", "").strip()
        api_token   = cfg.get("glassnote_api_token", "").strip()
        user_plan   = cfg.get("glassnote_user_plan", "free")

        if not api_url:
            return  # Not in SaaS mode — skip

        def _fetch():
            try:
                import httpx
                headers = {}
                if api_token:
                    headers["Authorization"] = f"Bearer {api_token}"

                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(8.0, connect=5.0),
                ) as c:
                    r = c.get(
                        f"{api_url}/api/notifications/active",
                        params={"plan": user_plan},
                        headers=headers,
                    )

                if r.status_code != 200:
                    return

                notifications = r.json()
                if not notifications:
                    return

                # Load dismissed IDs from config (persisted across restarts)
                dismissed = set(cfg.get("dismissed_notification_ids", []))

                new_notifs = [n for n in notifications if n["id"] not in dismissed]
                if new_notifs:
                    self._sig_notifications.emit(new_notifs)

            except Exception as e:
                print(f"[app] Notification poll failed (non-fatal): {e}")

        threading.Thread(target=_fetch, daemon=True, name="notif-poll").start()

    def _show_notifications(self, notifications: list):
        """
        Display notification banners for each new notification.

        BUG-10 fix: previously used overlay.set_error() which overwrites any
        active answer being streamed. Now uses overlay.show_notification_banner()
        which renders a non-destructive banner above the answer content.
        Falls back to pill tooltip if overlay has an active answer.

        When dismissed, its ID is written to config so it is not shown again.
        """
        cfg       = config.load_config()
        dismissed = set(cfg.get("dismissed_notification_ids", []))

        for notif in notifications:
            nid     = notif.get("id", "")
            title   = notif.get("title", "GlassNote Update")
            message = notif.get("message", "")
            ntype   = notif.get("type", "info")

            if nid in dismissed:
                continue

            type_icon = {"info": "ℹ", "warning": "⚠", "critical": "🔴"}.get(ntype, "ℹ")
            banner_text = f"{type_icon} **{title}** — {message}"

            # BUG-10 fix: use show_notification_banner() instead of set_error()
            # so active answers are not overwritten.
            if hasattr(self.overlay, "show_notification_banner"):
                self.overlay.show_notification_banner(banner_text, ntype)
                self.overlay.show()
                self.pill.set_overlay_visible(True)
            else:
                # Fallback: only show if overlay has no active answer
                if not self.overlay.isVisible():
                    self.overlay.set_error(
                        f"**{type_icon} {title}**\n\n{message}\n\n"
                        f"_(Dismiss to not show again)_"
                    )
                    self.overlay.show()
                    self.pill.set_overlay_visible(True)
                else:
                    # Don't overwrite active answer — log only
                    print(f"[app] Notification suppressed (overlay active): {title}")

            # Mark as dismissed
            dismissed.add(nid)
            print(f"[app] Notification shown: {title}")

        # Persist updated dismissed list
        cfg["dismissed_notification_ids"] = list(dismissed)
        config.save_config(cfg)

    # ── Launch ─────────────────────────────────────────────────────────────────

    def launch(self):
        """Launches the application by opening the initial session setup window."""
        self._open_session_setup()

    def _show_main_ui(self):
        self.pill.show()
        self.pill.start_session_clock()   # Bug 1 fix: start timer only when session begins
        self.pill.set_overlay_visible(self.overlay.isVisible())
        cfg = config.load_config()
        if cfg.get("auto_capture", False):
            self._watcher.start()

    # ── Capture ────────────────────────────────────────────────────────────────

    def _on_capture(self):
        if not session_manager.is_active():
            return
        try:
            b64   = screencap.capture_fullscreen()
            count = self._queue.add(b64)
            print(f"[app] Screenshot captured — queue={count}")
        except Exception as e:
            self.overlay.set_error(f"Screenshot failed: {e}")
            self.overlay.show()

    def _on_auto_capture(self, b64: str):
        if session_manager.is_active():
            self._queue.add(b64)

    # ── Solve ──────────────────────────────────────────────────────────────────

    def _on_solve(self):
        if not session_manager.is_active():
            return
        if self._queue.is_empty():
            self.overlay.set_error(
                "No screenshots queued.\n"
                "Press **Ctrl+Shift+C** to capture first."
            )
            self.overlay.show()
            return
        shots  = self._queue.pop_all()
        images = [s.b64_image for s in shots]
        label  = f"{len(images)} screenshot{'s' if len(images) > 1 else ''}"
        print(f"[app] SOLVE — {label}")
        self._dispatch_llm(
            images=images,
            mode="solve",
            label=label,
            question=f"Solving {label}",
        )

    # ── Analyze ────────────────────────────────────────────────────────────────

    def _on_analyze(self):
        if not session_manager.is_active():
            return
        try:
            b64 = screencap.capture_fullscreen()
            print("[app] ANALYZE — instant capture")
            self._dispatch_llm(
                images=[b64],
                mode="analyze",
                label="Screen Analysis",
                question="Analyzing current screen",
            )
        except Exception as e:
            self.overlay.set_error(f"Capture failed: {e}")
            self.overlay.show()

    # ── Interview ──────────────────────────────────────────────────────────────

    def _on_interview_toggle(self):
        if not session_manager.is_active():
            return
        if not self._recording:
            self._start_continuous_recording()
        else:
            self._stop_continuous_recording()

    def _start_continuous_recording(self):
        """
        Enter interview mode by opening the pipeline gate.

        If the pipeline is not yet running (first time), start it and warm
        the LLM connection.  On subsequent toggles, just call resume() which
        is essentially instant (< 1 ms) — no pipeline teardown/rebuild.

        Bug E fix: always call pill.set_recording(True) and
        pill.set_continuous_mode(True) here, regardless of whether the
        pipeline was already running.  On the first toggle, start_recording()
        emits recording_started → _on_recording_started(), but that handler
        is now guarded by self._recording (Bug A fix) so it will also call
        these methods.  On subsequent toggles (pipeline already warm),
        recording_started is NOT re-emitted, so we must call them directly.
        Calling them twice on the first toggle is harmless (idempotent).
        """
        self._recording = True
        cfg    = config.load_config()
        source = cfg.get("audio_source", "system")

        if not self._audio.is_running():
            # First entry: start the full pipeline (runs once per session)
            # Note: STT DNS pre-resolution happens in _prefetch_stt_and_start()
            llm_client.warm_connections(cfg=cfg)
            self._audio.start_recording(source=source)

        # Always update UI — covers both first-time and subsequent toggles.
        # On first toggle: _on_recording_started() also calls these (harmless).
        # On subsequent toggles: pipeline is already running, so this is the
        # only place these get called.
        self.pill.set_recording(True)
        self.pill.set_continuous_mode(True)

        # Open the dispatch gate — instant on subsequent toggles
        self._audio.resume()

        # TTFT-OPT: Only start silence timer when smart_answering=False.
        # When using STT end-of-turn signals (smart_answering=True), the
        # silence timer is redundant — STT dispatches directly on [EndOfTurn].
        # Saves 1-2ms per request by avoiding 10 unnecessary timer checks/sec.
        if not cfg.get("smart_answering", False):
            self._silence_timer.start()

        print(f"[app] Interview mode started — source={source}")

    def _stop_continuous_recording(self):
        """Exit interview mode by closing the gate (pipeline stays warm)."""
        self._recording = False
        self._silence_timer.stop()

        # Fix 2: In manual mode (smart_answering=False), the silence timer is
        # the sole dispatch trigger.  Stopping it before it fires discards any
        # accumulated transcript.  Fetch and dispatch it now so the user always
        # gets an answer when they click "Stop".
        cfg = config.load_config()
        if not cfg.get("smart_answering", False):
            text = self._audio.get_accumulated_transcript()
            if text and text.strip():
                self._on_transcript_ready(text.strip())

        self._audio.pause()   # close gate; keeps STT WebSocket alive
        self.pill.set_recording(False)
        self.pill.set_solving(False, mode="solve")
        self.pill.set_continuous_mode(False)   # Fix 3: hide ticker window
        print("[app] Interview mode stopped")


    # ── STT warm connection ────────────────────────────────────────────────────

    def _warm_stt_connection(self, cfg: dict):              # ← NEW METHOD
        """
        Pre-resolve DNS for STT provider to warm OS DNS cache.

        The previous implementation created a throwaway httpx.Client and did
        a full HTTPS GET, but the TCP+TLS connection was discarded immediately
        and NOT reused by the STT WebSocket — so the warm-up was wasted.

        DNS resolution, on the other hand, IS cached by the OS resolver and
        shared across all libraries (httpx, websockets, etc.).  A single
        socket.getaddrinfo() call populates the OS DNS cache so the WebSocket
        handshake skips the DNS lookup (~50-200 ms saved).

        Provider behaviour:
          deepgram        → pre-resolve api.deepgram.com
          openai_realtime → pre-resolve api.openai.com

        Always non-blocking — runs in a daemon thread.
        Failures are non-fatal and logged only; recording still starts.
        """
        stt_provider = cfg.get("stt_provider", "deepgram")

        def _warm():
            try:
                t0 = time.time()
                hosts = []

                if stt_provider == "deepgram":
                    hosts.append("api.deepgram.com")
                elif stt_provider == "openai_realtime":
                    hosts.append("api.openai.com")
                else:
                    # Unknown provider — try both as best-effort
                    hosts.append("api.deepgram.com")
                    hosts.append("api.openai.com")

                for host in hosts:
                    socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)

                ms = (time.time() - t0) * 1_000
                print(
                    f"[app] ✓ STT DNS pre-resolved — {', '.join(hosts)} "
                    f"{ms:.0f} ms"
                )

            except Exception as e:
                print(f"[app] STT DNS pre-resolve failed (non-fatal): {e}")

        threading.Thread(
            target=_warm,
            daemon=True,
            name="stt-warm",
        ).start()

    def _speculative_warm(self, cfg: dict):
        """
        Speculative connection warming — fired on session start.

        Pre-warms TCP+TLS connections to:
          1. LLM provider (Anthropic or OpenAI)
          2. GlassNote API proxy (if user is authenticated in SaaS mode)

        This runs in a background thread and completes in ~200ms.
        By the time the user triggers their first solve/analyze/interview,
        the connection is already established — saving 80-200ms TTFT.

        Args:
            cfg (dict): Pre-loaded config dict.
        """
        try:
            # 1. Warm LLM provider connection
            llm_client.warm_connections(cfg=cfg)
            print("[app] ✓ Speculative warm — LLM provider connection initiated")

            # 2. Warm GlassNote proxy (SaaS mode)
            proxy_token = cfg.get("glassnote_api_token", "").strip()
            proxy_url   = cfg.get("glassnote_api_url", "").strip()
            if proxy_token and proxy_url:
                import httpx
                t0 = time.time()
                with httpx.Client(
                    http2=True,
                    timeout=httpx.Timeout(6.0, connect=5.0),
                ) as c:
                    r = c.get(
                        f"{proxy_url}/health",
                        headers={"Authorization": f"Bearer {proxy_token}"},
                    )
                ms = (time.time() - t0) * 1_000
                print(
                    f"[app] ✓ Speculative warm — GlassNote proxy "
                    f"{ms:.0f} ms (status={r.status_code})"
                )

        except Exception as e:
            print(f"[app] Speculative warm failed (non-fatal): {e}")

    # ── Audio pipeline callbacks ───────────────────────────────────────────────

    def _on_connection_ready(self):
        """PERF-6: Called on main thread when warm-up completes — pill dot turns green.

        Issue 1 fix: pill is now shown immediately in _on_session_started() with
        an amber warming dot.  This handler only updates the dot colour to green.
        """
        self.pill.set_connection_status("ready")
        print("[app] ✓ Connections warm — ready for interview mode")
        # Pill is already visible (shown in _on_session_started) — nothing else needed.

    def _on_warmup_timeout(self):
        """Fallback: ensure pill is visible if warm-up signal never fires (15 s guard)."""
        if not self._pill_shown:
            print("[app] Warm-up timeout — showing pill anyway")
            self._pill_shown = True
            self._show_main_ui()

    def _on_recording_started(self):
        # Bug A fix: only show ticker/recording state when the user has
        # actually toggled Interview Mode on (_recording=True).
        # On session start, start_recording() is called for warm-up while
        # _recording is still False — we must NOT show the ticker then.
        if self._recording:
            self.pill.set_recording(True)
            self.pill.set_continuous_mode(True)

    def _on_recording_stopped(self):
        self.pill.set_recording(False)
        self.pill.set_continuous_mode(False)

    # ── Silence check — fires every 100 ms ────────────────────────────────────

    def _check_silence(self):
        if not self._recording:
            self._silence_timer.stop()
            return

        age       = self._audio.get_last_transcript_age()
        # PERF: Read threshold from pipeline's cached value instead of
        # calling config.load_config() every 100 ms (disk I/O on hot path).
        # AudioPipeline caches this in _silence_threshold on start and refresh_config().
        threshold = getattr(self._audio, '_silence_threshold', 1.5)
        self.pill.update_ticker_silence(age, threshold)

        # pipeline.check_silence_and_dispatch() handles all guards internally.
        # When smart_answering=True and STT already dispatched, the pipeline's
        # _processing_question=True guard exits in < 1 µs — no wasted work.
        self._audio.check_silence_and_dispatch()

    # ── Partial transcript → pill ticker ──────────────────────────────────────

    def _on_partial_transcript(self, text: str):
        if not text.strip():
            return

        self.pill.update_ticker_partial(text)

        user_speaking = self._audio.is_user_speaking()
        processing    = self._audio.is_processing()

        if processing and user_speaking:
            self.pill.ticker.set_status_user_speaking()
        elif processing:
            self.pill.ticker.set_status_answering()
        elif user_speaking:
            self.pill.ticker.set_status_user_speaking()
        else:
            self.pill.ticker.set_status_listening()

    # ── Transcript ready → dispatch LLM ───────────────────────────────────────

    def _on_transcript_ready(self, transcript: str):
        self.pill.commit_ticker_segment(transcript)

        session = session_manager.get()
        if not session:
            return

        cfg = config.load_config()
        smart = cfg.get("smart_answering", True)
        context_window = int(cfg.get("interview_context_window", 5))

        # TTFT-OPT: When smart_answering=True, use a sliding window of recent
        # conversation history instead of the entire session. This balances:
        #   - Speed: ~500-800ms TTFT (vs 2000+ ms with full history)
        #   - Context: Recent Q&As available for follow-up questions
        #   - Token count: ~1000-1500 tokens (vs 5000+ with full history)
        #
        # When smart_answering=False, include full history for maximum context.
        if smart and context_window >= 0:
            # Sliding window mode: keep last N Q&A exchanges
            full_history = session.get_history_context()
            # Each Q&A pair = 2 messages (user + assistant)
            # window_size = context_window exchanges * 2 messages per exchange
            window_size = context_window * 2

            if context_window == 0:
                # No context mode: single-turn only (fastest)
                messages = []
                print("[app] Interview mode: no context (single-turn)")
            elif len(full_history) > window_size:
                messages = full_history[-window_size:]
                print(f"[app] Interview context window: {len(messages)} messages (last {context_window} Q&As)")
            else:
                messages = full_history

            messages.append({
                "role":    "user",
                "content": (
                    f"The other person just said:\n\n\"{transcript}\"\n\n"
                    "Please provide a clear, structured answer I can speak naturally."
                ),
            })
        else:
            # Full context mode: include entire conversation history
            # (either smart_answering=False or context_window=-1)
            messages = session.get_history_context()
            messages.append({
                "role":    "user",
                "content": (
                    f"The other person just said:\n\n\"{transcript}\"\n\n"
                    "Please provide a clear, structured answer I can speak naturally."
                ),
            })
            if smart:
                print("[app] Interview mode: unlimited context (full history)")

        label = (
            f'"{transcript[:40]}..."'
            if len(transcript) > 40
            else f'"{transcript}"'
        )

        self._dispatch_llm(
            images=[],
            mode="interview",
            label=label,
            messages_override=messages,
            question=transcript,
        )

    def _on_transcribe_error(self, message: str):
        # Only treat as fatal (kill interview mode + show error overlay) when
        # the error is a hard failure: missing/invalid API key, or the pipeline
        # is no longer running.  Transient WebSocket drops are now handled by
        # the STT auto-reconnect loop and never reach here.  If somehow a
        # non-fatal error does arrive while the pipeline is still live, just
        # log it so the user isn't interrupted mid-interview.
        fatal_keywords = (
            "No Deepgram API key",
            "No OpenAI API key",
            "Deepgram init failed",
            "OpenAI Realtime STT init failed",
            "Unknown STT provider",
            "no longer supported",
        )
        is_fatal = any(kw in message for kw in fatal_keywords)

        if not is_fatal and self._audio.is_running():
            # Transient error — pipeline still alive, STT will reconnect.
            print(f"[app] STT transient error (non-fatal, pipeline still running): {message}")
            return

        # Fatal or pipeline dead — tear down interview mode and show error.
        self.pill.set_transcribing(False)
        self.pill.set_recording(False)
        self._recording = False
        self._silence_timer.stop()
        self.overlay.set_error(f"Transcription failed:\n{message}")
        self.overlay.show()
        self.pill.set_overlay_visible(True)

    # ── Overlay toggle ─────────────────────────────────────────────────────────

    def _on_toggle_overlay(self):
        self.overlay.toggle_visibility()
        self.pill.set_overlay_visible(self.overlay.isVisible())

    def _on_toggle_pill(self):
        if self.pill.isVisible():
            self.pill.hide()
            self.overlay.hide()
            self.pill.set_overlay_visible(False)
        else:
            if session_manager.is_active():
                self.pill.show()

    # ── Move ───────────────────────────────────────────────────────────────────

    def _on_move(self, direction: str):
        self.pill.move_by(direction)
        self.overlay.move_by(direction)

    # ── Settings ───────────────────────────────────────────────────────────────

    def _on_open_settings(self):
        if self._settings_window and self._settings_window.isVisible():
            self._settings_window.raise_()
            return
        from settings.ui import SettingsWindow
        self._settings_window = SettingsWindow()
        self._settings_window.settings_saved.connect(self._on_settings_saved)
        self._settings_window.show()

    def _on_settings_saved(self):
        cfg = config.load_config()

        # ── Apply immediate UI / watcher changes ───────────────────────────────
        self._watcher.set_interval(cfg.get("auto_capture_interval", 5))
        self.overlay.set_opacity(float(cfg.get("opacity", 0.96)))

        # ── Invalidate caches so new values take effect on next call ──────────
        llm_client.invalidate_config()
        self._audio.refresh_config()

        # ── Clear memoised prompts so session context changes propagate ───────
        prompts.clear_prompt_cache()                   # ← NEW

        print("[app] Settings saved — all caches invalidated")

    # ── Session ────────────────────────────────────────────────────────────────

    # ── Session duration enforcement ───────────────────────────────────────────

    def _check_session_duration(self):
        """
        Called every 30 s while a session is active.

        Computes remaining time against the pre-calculated _session_end_time:
          - At ≤ 5 minutes remaining: show a non-destructive warning banner
            in the overlay (shown only once per session).
          - At ≤ 0 seconds remaining: auto-end the session and show a final
            notice so the user knows why the session closed.
        """
        if not session_manager.is_active():
            self._session_timer.stop()
            return

        # 0.0 means unlimited — nothing to check
        if self._session_end_time == 0.0:
            return

        remaining = self._session_end_time - time.time()

        if remaining <= 0:
            # Time's up — auto-end
            print("[app] Session time limit reached — auto-ending session")
            self._session_timer.stop()
            # Show a brief notice in the overlay before tearing down
            try:
                self.overlay.show_notification_banner(
                    "⏱ **Session time limit reached** — session ended automatically.",
                    "warning",
                )
                self.overlay.show()
                self.pill.set_overlay_visible(True)
            except Exception:
                pass
            # Delay the actual teardown by 2 s so the user can read the notice
            QTimer.singleShot(2_000, lambda: self._on_end_session(relaunch=True))
            return

        # 5-minute warning (shown once)
        if remaining <= 5 * 60 and not self._session_warn_shown:
            self._session_warn_shown = True
            mins_left = max(1, int(remaining // 60))
            warn_text = (
                f"⏱ **{mins_left} minute{'s' if mins_left != 1 else ''} remaining** "
                f"— your session will auto-end soon."
            )
            print(f"[app] Session expiry warning — {mins_left} min remaining")
            try:
                if hasattr(self.overlay, "show_notification_banner"):
                    self.overlay.show_notification_banner(warn_text, "warning")
                    self.overlay.show()
                    self.pill.set_overlay_visible(True)
                else:
                    # Fallback: set as error text only if overlay is not streaming
                    if not self.overlay.isVisible():
                        self.overlay.set_error(warn_text)
                        self.overlay.show()
                        self.pill.set_overlay_visible(True)
            except Exception as e:
                print(f"[app] Warning banner failed (non-fatal): {e}")

    def _on_end_session(self, relaunch: bool = True):
        session = session_manager.get()
        session_id = getattr(session, "id", "") or ""
        llm_streamer.cancel()
        llm_client.stop_keepalive()
        self.pill.set_solving(False, mode="solve")
        self._watcher.stop()
        self._audio.stop_recording()   # full teardown (not just pause)
        self._silence_timer.stop()
        self._session_timer.stop()     # stop duration countdown
        session_manager.end()
        hotkey_manager.stop()
        self._queue.clear()
        self._recording = False
        self._pill_shown = False
        self._session_end_time   = 0.0
        self._session_warn_shown = False
        self.pill.stop_session_clock()    # Bug 1 fix: stop + reset timer on session end
        self.pill.hide()
        self.overlay.hide()
        self.session_status_changed.emit(False, "")

        # ── Print session performance summary ─────────────────────────────
        summary = perf_tracker.get_summary_line()
        print(f"[app] Session ended — {summary}")

        # ── Report usage to GlassNote backend (async, non-blocking) ────────
        cfg = config.load_config()
        proxy_url   = cfg.get("glassnote_api_url", "").strip()
        proxy_token = cfg.get("glassnote_api_token", "").strip()
        if proxy_url and proxy_token and session:
            from api.usage_reporter import report_session_usage
            raw_calls  = perf_tracker.get_calls_raw()

            # Build conversation JSON from Q&A history (no real screenshots)
            conversation_json = []
            session_summary   = ""
            if session.history:
                for qa in session.history:
                    conversation_json.append({
                        "question":    qa.question_summary,
                        "answer":      qa.answer[:2000],
                        "screenshots": ["[Screenshot Placeholder]"] * len(qa.screenshots),
                    })
                session_summary = session.history[-1].answer[:300]

            report_session_usage(
                api_url=proxy_url,
                api_token=proxy_token,
                session_id=session_id,
                perf_summary=perf_tracker.get_session_stats(),
                stt_calls=[c for c in raw_calls if c.get("type") == "stt"],
                llm_calls=[c for c in raw_calls if c.get("type") == "llm"],
                session_summary=session_summary,
                conversation_json=conversation_json,
            )

        # PERF-5: Clear cached user info on session end
        self._cached_user_info = {}
        # PERF-6: Reset connection status indicator
        self.pill.set_connection_status("")

        perf_tracker.reset()

        if relaunch:
            QTimer.singleShot(300, self._open_session_setup)

    def _open_session_setup(self):
        from session.setup_ui import SessionSetupWindow
        self._session_window = SessionSetupWindow()
        self._session_window.open_settings.connect(self._on_open_settings)
        self._session_window.session_started.connect(self._on_session_started)
        self._session_window.show()

    def _on_session_started(self):
        """
        Called when user finishes session setup (AFTER backend confirms session).

        BUG-6 fix: audio pipeline warm-up now happens AFTER backend confirms
        the session via /api/sessions/start. Previously it fired unconditionally
        in _on_session_started which ran before the 402 check completed.

        PERF-2 fix: STT credentials are pre-fetched here in a background thread
        and injected into the config before the pipeline starts, so _create_stt()
        never blocks the pipeline thread on a synchronous HTTP call.

        Immediately fires connection pre-warming in background threads:
          1. LLM provider (Anthropic/OpenAI) — TCP+TLS handshake
          2. GlassNote proxy (if SaaS mode) — TCP+TLS to api.glassnote.ai
          3. STT credentials pre-fetch (BUG-9/PERF-2 fix)
        """
        print("[app] Session started!")
        session = session_manager.get()
        label   = session.company or "Active Session" if session else "Active Session"
        self.session_status_changed.emit(True, label)
        if not hotkey_manager._registered:
            hotkey_manager.start()

        cfg = config.load_config()

        # ── Session duration enforcement ───────────────────────────────────────
        # Read the max duration stored in config by setup_ui._on_session_registered
        # (key: _session_max_duration_minutes).  0 = unlimited plan.
        # session.started_at is the Unix timestamp set in SessionManager.start().
        max_minutes = int(cfg.get("_session_max_duration_minutes", 0) or 0)
        if max_minutes > 0 and session:
            self._session_end_time   = session.started_at + (max_minutes * 60)
            self._session_warn_shown = False
            self._session_timer.start()
            end_ts = time.strftime("%H:%M", time.localtime(self._session_end_time))
            print(
                f"[app] Session duration limit: {max_minutes} min "
                f"— auto-ends at {end_ts}"
            )
        else:
            self._session_end_time   = 0.0
            self._session_warn_shown = False
            self._session_timer.stop()
            print("[app] Session duration: unlimited")

        # Issue 1 fix: show pill immediately with amber warming dot so the user
        # has visual feedback while background connections are being established.
        # Previously the pill only appeared after _on_connection_ready() fired
        # (~3–5 s later), leaving the UI frozen with no feedback.
        if not self._pill_shown:
            self._pill_shown = True
            self._show_main_ui()
        self.pill.set_connection_status("warming")

        # ── Speculative connection pre-warming ─────────────────────────────────
        # Fire in background — returns immediately, completes in ~200ms.
        # This way the first LLM call doesn't pay the TCP+TLS cost.
        threading.Thread(
            target=self._speculative_warm,
            args=(cfg,),
            daemon=True,
            name="speculative-warm",
        ).start()

        # ── STT credentials pre-fetch + audio pipeline warm start ─────────────
        # BUG-9/PERF-2 fix: fetch STT credentials from backend BEFORE starting
        # the pipeline so _create_stt() never blocks on a synchronous HTTP call.
        # The credentials are injected into a copy of cfg passed to the pipeline.
        # Audio pipeline starts in paused state for 0ms warmup on Interview Mode.
        # TTFT-OPT: DNS pre-resolution now runs in parallel with credential
        # fetches inside _prefetch_stt_and_start() instead of before it.
        source = cfg.get("audio_source", "system")

        def _prefetch_stt_and_start():
            """Pre-fetch STT credentials then start pipeline (BUG-9/PERF-2).

            PERF-7: /api/auth/me and /v1/proxy/stt-credentials are now fired
            in parallel using ThreadPoolExecutor, saving ~200-500 ms on
            session startup (previously sequential).
            """
            cfg2 = config.load_config()
            plan = cfg2.get("glassnote_user_plan", "free").strip() or "free"
            is_byok = (plan == "byok")

            try:
                import httpx as _httpx
                from api.auth_client import _keyring_load
                token   = _keyring_load() or cfg2.get("glassnote_api_token", "")
                api_url = cfg2.get("glassnote_api_url", "").rstrip("/")

                # ── Helper: fetch /api/auth/me ──────────────────────────────
                def _fetch_auth_me():
                    """Fetch and cache user info from /api/auth/me."""
                    if not (token and api_url):
                        return None
                    try:
                        r_me = _httpx.get(
                            f"{api_url}/api/auth/me",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=5.0,
                        )
                        if r_me.status_code == 200:
                            data = r_me.json()
                            print(f"[app] /api/auth/me cached (plan={data.get('plan','?')})")
                            return data
                    except Exception as e:
                        print(f"[app] /api/auth/me cache failed (non-fatal): {e}")
                    return None

                # ── Helper: fetch /v1/proxy/stt-credentials ─────────────────
                def _fetch_stt_creds():
                    """Fetch STT credentials from proxy."""
                    if is_byok or not (token and api_url):
                        return None
                    try:
                        r = _httpx.get(
                            f"{api_url}/v1/proxy/stt-credentials",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=8.0,
                        )
                        if r.status_code == 200:
                            data = r.json()
                            print(f"[app] STT credentials pre-fetched (plan={plan})")
                            return data
                        else:
                            print(f"[app] STT credentials pre-fetch failed ({r.status_code}) — using local keys")
                    except Exception as e:
                        print(f"[app] STT credentials pre-fetch error: {e} — using local keys")
                    return None

                # ── Helper: DNS pre-resolution for STT ──────────────────────
                def _warm_dns():
                    """Pre-resolve DNS for STT provider to warm OS DNS cache."""
                    stt_provider = cfg2.get("stt_provider", "deepgram")
                    try:
                        t0 = time.time()
                        hosts = []
                        if stt_provider == "deepgram":
                            hosts.append("api.deepgram.com")
                        elif stt_provider == "openai_realtime":
                            hosts.append("api.openai.com")
                        else:
                            hosts.append("api.deepgram.com")
                            hosts.append("api.openai.com")

                        for host in hosts:
                            socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)

                        ms = (time.time() - t0) * 1_000
                        print(f"[app] ✓ STT DNS pre-resolved — {', '.join(hosts)} {ms:.0f} ms")
                    except Exception as e:
                        print(f"[app] STT DNS pre-resolve failed (non-fatal): {e}")

                # ── Fire all three operations in parallel ───────────────────
                # TTFT-OPT: DNS pre-resolution now runs concurrently with
                # credential fetches instead of after. Saves 50-200ms.
                with ThreadPoolExecutor(max_workers=3) as pool:
                    fut_me    = pool.submit(_fetch_auth_me)
                    fut_creds = pool.submit(_fetch_stt_creds)
                    fut_dns   = pool.submit(_warm_dns)
                    me_result    = fut_me.result()
                    creds_result = fut_creds.result()
                    fut_dns.result()  # Wait for DNS warm-up to complete

                # ── Apply results ───────────────────────────────────────────
                if me_result is not None:
                    self._cached_user_info = me_result

                if creds_result is not None:
                    if creds_result.get("deepgram_key"):
                        cfg2["deepgram_api_key"] = creds_result["deepgram_key"]
                    if creds_result.get("openai_key"):
                        cfg2["openai_api_key"] = creds_result["openai_key"]

                # Inject pre-fetched credentials into pipeline config before start
                self._audio.set_prefetched_config(cfg2)
                # Start pipeline in paused state — gate closed, STT WebSocket warm.
                # Use the signal to cross the thread boundary safely (Qt-safe).
                self._sig_start_pipeline.emit()
            except Exception as e:
                print(f"[app] Warm-up error (non-fatal): {e}")
            finally:
                # PERF-6: Signal ready after warm-up completes (guaranteed)
                self._sig_connection_ready.emit()

        threading.Thread(
            target=_prefetch_stt_and_start,
            daemon=True,
            name="stt-prefetch",
        ).start()
        QTimer.singleShot(15_000, self._on_warmup_timeout)
        print(f"[app] Audio pipeline warm start scheduled — source={source}")

    # ── Core LLM dispatch ──────────────────────────────────────────────────────

    def _dispatch_llm(
        self,
        images:            list,
        mode:              str  = "solve",
        label:             str  = "",
        messages_override: list = None,
        question:          str  = "",
    ):
        """
        Dispatches a query to the configured LLM provider (Anthropic or OpenAI).
        Constructs the appropriate system prompt based on the session state and 
        handles streaming the response back to the overlay UI.

        Args:
            images (list): Base64 encoded images to send to the vision model.
            mode (str): The operational mode ('solve', 'analyze', 'interview').
            label (str): Label used in the UI to describe the current task.
            messages_override (list, optional): Overrides the default chat history.
            question (str): The textual query or transcript being processed.
        """
        session = session_manager.get()
        if not session:
            return

        cfg          = config.load_config()
        smart        = cfg.get("smart_answering", True)    # Bug 2 fix: default True (lean prompt, ~400ms TTFT vs ~2000ms)
        base         = session.build_system_prompt()
        provider     = cfg.get("selected_provider", "anthropic")
        text_only    = (provider == "cerebras")  # Cerebras models don't support images

        # ── Prompt selection ───────────────────────────────────────────────────
        if mode == "analyze":
            system_prompt = prompts.build_analyze_prompt(base, text_only=text_only)
        elif mode == "interview":
            # ← CHANGED: lean prompt when smart_answering=True
            # Lean prompt: ~80 tokens → saves 100–400 ms TTFT on Haiku.
            # Full prompt: ~400–1200 tokens → includes session context.
            system_prompt = (
                prompts.build_interview_prompt_lean()
                if smart
                else prompts.build_interview_prompt(base)
            )
        else:
            system_prompt = prompts.build_solve_prompt(base, text_only=text_only)

        # ── Messages ───────────────────────────────────────────────────────────
        if messages_override:
            messages = messages_override
        else:
            messages = session.get_history_context()
            messages.append({
                "role":    "user",
                "content": (
                    "Please analyze the provided screenshot(s) and solve the problem."
                    if images else
                    "Please help me with this question."
                ),
            })

        # ── UI — start streaming display ───────────────────────────────────────
        self.pill.set_solving(True, mode=mode)
        self.overlay.start_stream(label=label, question=question)
        self.overlay.show()
        self.pill.set_overlay_visible(True)

        self._current_answer      = ""
        self._dispatch_start_time = time.time()
        self._dispatch_mode       = mode

        # Resolve model name for perf tracking (mirrors logic in llm/client.py)
        provider = cfg.get("selected_provider", "anthropic")
        if provider == "anthropic":
            self._dispatch_model = cfg.get("anthropic_model", "claude-opus-4-5")
        elif provider == "cerebras":
            self._dispatch_model = cfg.get("cerebras_model", "llama3.1-8b")
        else:
            self._dispatch_model = cfg.get("openai_model", "gpt-4o")

        use_cache = cfg.get("use_response_cache", True)

        # ── Callbacks ─────────────────────────────────────────────────────────

        def on_token(token: str):
            self._current_answer += token
            self.overlay.append_token(token)

        def on_done(full_text: str):
            elapsed = (time.time() - self._dispatch_start_time) * 1_000
            print(f"[app] Answer complete — wall time {elapsed:.0f} ms")
            self.pill.set_solving(False, mode=mode)
            self.overlay.finish_stream(label)

            # ── Record in performance tracker ─────────────────────────────
            # Approximate output tokens from character count (~4 chars/token)
            approx_output_tokens = max(len(full_text) // 4, 1)
            perf_tracker.record_llm_call(
                model         = self._dispatch_model,
                mode          = self._dispatch_mode,
                latency_ms    = elapsed,
                output_tokens = approx_output_tokens,
            )

            if session_manager.is_active():
                session_manager.get().add_to_history(label, full_text)

            if mode == "interview" and self._recording:
                self._audio.notify_llm_done()
                print("[app] Mic still open — listening for next question")

        def on_error(message: str):
            self.pill.set_solving(False, mode=mode)
            self.overlay.set_error(message)
            if mode == "interview" and self._recording:
                self._audio.notify_llm_done()

        # ── Fire ───────────────────────────────────────────────────────────────
        llm_streamer.solve(
            system_prompt = system_prompt,
            messages      = messages,
            images        = images if images else None,
            on_token      = on_token,
            on_done       = on_done,
            on_error      = on_error,
            use_cache     = use_cache,
            mode          = mode,
        )