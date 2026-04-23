# ===== File: settings/ui.py =====
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QCheckBox, QTabWidget,
    QFrame, QSpinBox, QDoubleSpinBox, QScrollArea, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings import config
from utils import theme as th
import pricing_config as pricing


# ── Small helpers ──────────────────────────────────────────────────────────────

def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setObjectName("h_sep")
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _note(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("note_label")
    lbl.setWordWrap(True)
    return lbl


# ──────────────────────────────────────────────────────────────────────────────

class SettingsWindow(QWidget):
    """
    The main settings UI window.
    Provides tabs to configure API keys, AI models, audio source options, 
    overlay styling, and capture behaviors for GlassNote.
    """
    settings_saved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg         = config.load_config()
        self._user_plan  = self.cfg.get("glassnote_user_plan", "").strip()
        self._user_email = self.cfg.get("glassnote_user_email", "").strip()
        self._drag_pos   = None
        self._build_ui()
        self._refresh_theme()
        if self._user_plan:
            self._show_settings()
        else:
            self._show_login_wall()

    def _show_login_wall(self):
        self._stack.setCurrentIndex(0)

    def _show_settings(self):
        self.cfg         = config.load_config()
        self._user_plan  = self.cfg.get("glassnote_user_plan", "free").strip() or "free"
        self._user_email = self.cfg.get("glassnote_user_email", "").strip()
        self._stack.setCurrentIndex(1)
        self._load_values()
        self._apply_plan_restrictions()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Constructs the settings tabs and connects UI components."""
        self.setWindowTitle("GlassNote — Settings")
        self.setMinimumSize(560, 620)
        self.setFont(QFont("Segoe UI", 11))
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_title_bar())

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # Page 0: login wall
        wall = QWidget(); wall.setObjectName("login_wall")
        wl = QVBoxLayout(wall)
        wl.setContentsMargins(50, 70, 50, 70)
        wl.setSpacing(16)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Logo.png")
        wi = QLabel(); wi.setObjectName("wall_icon")
        wi.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _px = QPixmap(_LOGO_PATH)
        if not _px.isNull():
            wi.setPixmap(_px.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            wi.setText("\u25c8")  # fallback if logo file missing
        wl.addWidget(wi)
        wt = QLabel("Sign In to Access Settings")
        wt.setObjectName("wall_title")
        wt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.addWidget(wt)
        wd = QLabel("Settings and AI features are tied to your GlassNote account.")
        wd.setObjectName("wall_desc"); wd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wd.setWordWrap(True); wl.addWidget(wd)
        self._wall_btn = QPushButton("\U0001f511  Sign In / Create Account")
        self._wall_btn.setObjectName("primary")
        self._wall_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wall_btn.clicked.connect(self._open_login)
        wl.addWidget(self._wall_btn)
        self._stack.addWidget(wall)  # index 0

        # Page 1: full tabbed settings
        sp = QWidget()
        sl = QVBoxLayout(sp); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.tabs.addTab(self._tab_account(), "\U0001f464  Account")
        self.tabs.addTab(self._tab_models(),  "\U0001f916  Models")
        self.tabs.addTab(self._tab_audio(),   "\U0001f3a4  Audio")
        self.tabs.addTab(self._tab_overlay(), "\U0001f5a5  Overlay")
        self.tabs.addTab(self._tab_capture(), "\U0001f4f8  Capture")
        sl.addWidget(self.tabs)
        sl.addWidget(self._build_footer())
        self._stack.addWidget(sp)  # index 1


    def _build_title_bar(self) -> QWidget:
        self._title_bar_widget = QWidget()
        self._title_bar_widget.setObjectName("settings_title_bar")
        self._title_bar_widget.setFixedHeight(48)

        layout = QHBoxLayout(self._title_bar_widget)
        layout.setContentsMargins(20, 0, 12, 0)

        title = QLabel("⚙  Settings")
        title.setObjectName("settings_title_lbl")
        layout.addWidget(title)
        layout.addStretch()

        self._theme_btn = QPushButton("☀" if th.is_dark() else "🌙")
        self._theme_btn.setFixedSize(32, 32)
        self._theme_btn.setToolTip("Toggle dark / light mode")
        self._theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self._theme_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("settings_close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return self._title_bar_widget

    # ── Tab: Account ──────────────────────────────────────────────────────────

    def _tab_account(self) -> QWidget:
        w, layout, self._account_inner = self._scrollable_tab("account_inner")

        layout.addWidget(_section("GlassNote Account"))
        self._acct_status = QLabel("")
        self._acct_status.setObjectName("note_label")
        self._acct_status.setWordWrap(True)
        layout.addWidget(self._acct_status)

        acct_row = QHBoxLayout()
        self._btn_sign_out = QPushButton("\U0001f6aa  Sign Out")
        self._btn_sign_out.setObjectName("danger")
        self._btn_sign_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sign_out.clicked.connect(self._on_sign_out)
        acct_row.addWidget(self._btn_sign_out)

        dash_btn = QPushButton("\U0001f310  Open Dashboard")
        dash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dash_btn.clicked.connect(lambda: self._open_url("https://glassnote.ai/dashboard"))
        acct_row.addWidget(dash_btn)
        acct_row.addStretch()
        layout.addLayout(acct_row)

        layout.addWidget(_note(
            "Track usage, manage billing, and view session history at "
            "glassnote.ai/dashboard  \u2014  Profile and plan settings open in your browser."
        ))

        layout.addWidget(_sep())

        # BYOK API key fields
        self._byok_section_label = _section("Your API Keys  (BYOK Plan)")
        layout.addWidget(self._byok_section_label)
        self._byok_desc = _note(
            "Bring your own API keys for unlimited direct access. "
            "No per-session fee — you only pay your provider directly."
        )
        layout.addWidget(self._byok_desc)

        self._byok_anthro_label = _section("Anthropic (Claude)")
        layout.addWidget(self._byok_anthro_label)
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setPlaceholderText("sk-ant-...")
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.anthropic_key)

        self._byok_sep1 = _sep()
        layout.addWidget(self._byok_sep1)

        self._byok_openai_label = _section("OpenAI  (GPT \u00b7 Realtime STT)")
        layout.addWidget(self._byok_openai_label)
        self.openai_key = QLineEdit()
        self.openai_key.setPlaceholderText("sk-...")
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.openai_key)
        self._byok_openai_note = _note(
            "Required for GPT models and OpenAI Realtime STT "
            "(gpt-4o-transcribe / gpt-4o-mini-transcribe)."
        )
        layout.addWidget(self._byok_openai_note)

        self._byok_sep2 = _sep()
        layout.addWidget(self._byok_sep2)

        self._byok_dg_label = _section("Deepgram (Real-Time STT)")
        layout.addWidget(self._byok_dg_label)
        self.deepgram_key = QLineEdit()
        self.deepgram_key.setPlaceholderText("Token xxxxxxxxxxxxxxxx...")
        self.deepgram_key.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.deepgram_key)
        self._byok_dg_note = _note(
            "Deepgram provides ultra-low latency streaming transcription. "
            "Get a free key at deepgram.com \u2014 200 h free per month."
        )
        layout.addWidget(self._byok_dg_note)

        self._byok_widgets = [
            self._byok_section_label, self._byok_desc,
            self._byok_anthro_label, self.anthropic_key, self._byok_sep1,
            self._byok_openai_label, self.openai_key, self._byok_openai_note,
            self._byok_sep2,
            self._byok_dg_label, self.deepgram_key, self._byok_dg_note,
        ]

        byok_price = pricing.PLANS["byok"]["price_display"]
        self._byok_upsell = _note(
            f"\U0001f512  API key fields are available on the BYOK plan ({byok_price}).\n"
            "Your AI calls are routed through GlassNote's managed proxy. No keys needed!\n\n"
            "Want to use your own keys? Upgrade to BYOK at glassnote.ai."
        )
        layout.addWidget(self._byok_upsell)

        layout.addStretch()
        return w

    def _tab_api(self) -> QWidget:
        """Legacy alias kept for compatibility."""
        return self._tab_account()

    def _on_sign_out(self):
        """Sign out: clear keyring + config, return to login wall."""
        try:
            from api.auth_client import auth_client as _ac
            _ac.logout()
        except Exception:
            pass
        cfg = config.load_config()
        cfg.pop("glassnote_user_plan",  None)
        cfg.pop("glassnote_user_email", None)
        cfg.pop("glassnote_api_token",  None)   # also clear config token
        config.save_config(cfg)
        self._user_plan  = ""
        self._user_email = ""
        self._show_login_wall()


    # ── Tab: Models ────────────────────────────────────────────────────────────

    def _tab_models(self) -> QWidget:
        w, layout, self._models_inner = self._scrollable_tab("models_inner")

        # Plan info at top of models tab
        self._models_plan_info = _note("")
        layout.addWidget(self._models_plan_info)
        layout.addWidget(_sep())

        layout.addWidget(_section("Anthropic Model"))
        self.anthropic_model = QComboBox()
        # Populated dynamically in _populate_plan_models()
        layout.addWidget(self.anthropic_model)

        layout.addWidget(_sep())

        layout.addWidget(_section("OpenAI Model"))
        self.openai_model = QComboBox()
        # Populated dynamically in _populate_plan_models()
        layout.addWidget(self.openai_model)

        layout.addWidget(_sep())

        layout.addWidget(_section("Max Output Tokens"))
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(256, 8192)
        self.max_tokens.setSingleStep(256)
        layout.addWidget(self.max_tokens)

        layout.addWidget(_sep())

        layout.addWidget(_section("Smart Model Routing"))
        self.auto_model_routing = QCheckBox(
            "Auto-select cheaper model for simple questions"
        )
        layout.addWidget(self.auto_model_routing)
        layout.addWidget(_note(
            "Simple questions use Claude Haiku or GPT-4o Mini "
            "(2× faster, 10× cheaper). "
            "Complex algorithm / system design questions always "
            "use your selected model."
        ))

        layout.addStretch()
        return w

    def _populate_plan_models(self):
        """Populate Anthropic and OpenAI model dropdowns based on user plan."""
        allowed = pricing.get_allowed_models(self._user_plan)
        plan_data = pricing.get_plan(self._user_plan)

        # Split by provider
        anthro_models = [m[2] for m in allowed if m[1] == "anthropic"]
        openai_models = [m[2] for m in allowed if m[1] == "openai"]

        # Anthropic dropdown
        self.anthropic_model.clear()
        self.anthropic_model.addItems(anthro_models if anthro_models else ["claude-haiku-4-5"])

        # OpenAI dropdown
        self.openai_model.clear()
        self.openai_model.addItems(openai_models if openai_models else ["gpt-4o-mini"])

        # Plan info label
        plan_name = plan_data["display_name"]
        total = len(allowed)
        self._models_plan_info.setText(
            f"📋 {plan_name} Plan — {total} models available"
        )

        # Disable features not available on this plan
        if not pricing.is_feature_enabled(self._user_plan, "auto_model_routing"):
            self.auto_model_routing.setChecked(False)
            self.auto_model_routing.setEnabled(False)
            self.auto_model_routing.setToolTip(
                f"Smart routing requires the Starter plan or above"
            )
        else:
            self.auto_model_routing.setEnabled(True)
            self.auto_model_routing.setToolTip("")

    # ── Tab: Audio ─────────────────────────────────────────────────────────────

    def _tab_audio(self) -> QWidget:
        w, layout, self._audio_inner = self._scrollable_tab("audio_inner")

        # ── STT Provider ───────────────────────────────────────────────────────
        layout.addWidget(_section("Speech-to-Text Provider"))

        self.stt_provider = QComboBox()
        self.stt_provider.addItems([                                 # ← CHANGED (removed Whisper)
            "Deepgram (WebSocket — real-time, ultra-low latency, Best for Smart Answering)",
            "OpenAI Realtime  (server VAD — no hallucinations)",
        ])
        self.stt_provider.currentIndexChanged.connect(
            self._on_stt_provider_changed
        )
        layout.addWidget(self.stt_provider)

        self._stt_note = _note("")
        self._stt_note.setObjectName("stt_note")
        layout.addWidget(self._stt_note)

        layout.addWidget(_sep())

        # ── Deepgram model sub-section ─────────────────────────────────────────
        self._dg_model_section = _section("Deepgram Model")
        layout.addWidget(self._dg_model_section)

        self.deepgram_model = QComboBox()
        self.deepgram_model.addItems([
            "flux-general-en  (V2 API — ultra low latency ~80 ms, EndOfTurn events)",
            "nova-3           (V1 API — highest accuracy, speech_final events)",
            "nova-2           (V1 API — stable, widely supported)",
        ])
        layout.addWidget(self.deepgram_model)

        self._dg_model_note = _note(
            "flux-general-en: best for real-time — word appears as spoken.\n"
            "nova-3 / nova-2: higher accuracy with interim partial results."
        )
        layout.addWidget(self._dg_model_note)

        layout.addWidget(_sep())

        # ── OpenAI Realtime STT model sub-section ─────────────────────────────
        # NEW — shown only when "OpenAI Realtime" is selected as STT provider.
        self._oai_model_section = _section("OpenAI Realtime STT Model")  # ← NEW
        layout.addWidget(self._oai_model_section)

        self.openai_stt_model = QComboBox()                             # ← NEW
        self.openai_stt_model.addItems([
            "gpt-4o-mini-transcribe  ($0.003 / min — fastest + cheapest)",
            "gpt-4o-transcribe       ($0.006 / min — best accuracy)",
        ])
        layout.addWidget(self.openai_stt_model)

        self._oai_model_note = _note(                                   # ← NEW
            "Both use the OpenAI Realtime WebSocket API "
            "(wss://api.openai.com/v1/realtime?intent=transcription).\n\n"
            "• Server-side VAD — no silence hallucinations.\n"
            "• Streaming transcript deltas appear as speech is recognised.\n"
            "• 'transcription.completed' event fires when turn ends — "
            "works as Smart Answering trigger.\n\n"
            "gpt-4o-mini-transcribe is the recommended default: 50% cheaper "
            "than gpt-4o-transcribe with excellent quality for clear speech."
        )
        layout.addWidget(self._oai_model_note)

        layout.addWidget(_sep())

        # ── Audio Source ───────────────────────────────────────────────────────
        layout.addWidget(_section("Audio Source"))
        self.audio_source = QComboBox()
        self.audio_source.addItems([
            "system  (video call — captures interviewer via Stereo Mix)",
            "microphone  (in-person / phone call)",
            "both",
        ])
        layout.addWidget(self.audio_source)
        layout.addWidget(_note(
            "For 'system' to work: enable Stereo Mix in Windows Sound "
            "Settings (right-click speaker icon → Sounds → Recording tab)."
        ))

        layout.addWidget(_sep())

        # ── Auto Answer + Silence Threshold ───────────────────────────────────
        layout.addWidget(_section("Auto Answer"))
        self.auto_answer = QCheckBox(
            "Automatically send to AI after silence is detected"
        )
        layout.addWidget(self.auto_answer)
        # Issue 4b: dim silence_threshold when auto_answer is OFF
        self.auto_answer.toggled.connect(self._on_auto_answer_toggled)

        layout.addWidget(_section("Silence Threshold  (seconds)"))
        silence_row = QHBoxLayout()
        self.silence_threshold = QDoubleSpinBox()
        self.silence_threshold.setRange(0.5, 10.0)
        self.silence_threshold.setSingleStep(0.5)
        self.silence_threshold.setFixedWidth(100)
        silence_row.addWidget(self.silence_threshold)
        silence_row.addWidget(_note(
            "How long to wait after last word before auto-sending."
        ))
        layout.addLayout(silence_row)

        layout.addWidget(_sep())

        # ── Smart Answering ────────────────────────────────────────────────────
        layout.addWidget(_section("Smart Answering"))
        self.smart_answering = QCheckBox(
            "Use STT end-of-speech signal to trigger answers"
        )
        layout.addWidget(self.smart_answering)

        self.smart_answering.toggled.connect(self._on_smart_answering_toggled)

        # ← CHANGED: removed Whisper bullet, added OpenAI Realtime bullet
        self._smart_answering_note = _note(                             # ← store ref for dynamic updates
            "When ON, the STT provider's own end-of-utterance event is used "
            "together with the silence threshold to dispatch to the AI.\n\n"
            "Pair this smart signal with the ultra-low latency Deepgram flux-general-en model for best results — answers immediately at end of speech, not after a delay.\n\n"
            "• Deepgram flux-general-en  → EndOfTurn event  (V2 API)\n"
            "• Deepgram nova-3 / nova-2  → speech_final=True  (V1 API)\n"
            "• OpenAI Realtime           → transcription.completed  (server VAD)\n\n"
            "Both signals are OR-ed — whichever fires first triggers dispatch. "
            "The silence threshold remains active as a safety-net fallback."
        )
        layout.addWidget(self._smart_answering_note)

        layout.addStretch()
        return w

    # ── Smart Answering toggle callback ────────────────────────────────────────

    def _on_auto_answer_toggled(self, checked: bool):
        """
        Issue 4b: Disable / dim the silence-threshold spinbox when
        auto_answer is OFF.  When auto_answer=False the silence timer
        never fires — the user must stop interview mode to get an answer —
        so the threshold value has no effect and should appear inactive.
        """
        self.silence_threshold.setEnabled(checked)
        self.silence_threshold.setStyleSheet(
            "" if checked
            else "QDoubleSpinBox { opacity: 0.45; }"
        )
        self.silence_threshold.setToolTip(
            "How long to wait after last word before auto-sending."
            if checked else
            "Auto-answer is OFF — silence threshold has no effect.\n"
            "Stop interview mode to trigger an AI answer."
        )

    def _on_smart_answering_toggled(self, checked: bool):
        """
        Dims the silence-threshold spinbox when Smart Answering is ON to
        signal it becomes a fallback rather than the sole trigger.
        The spinbox stays enabled — it is still used as a safety net.
        """
        self.silence_threshold.setStyleSheet(
            "" if not checked
            else "QDoubleSpinBox { opacity: 0.55; }"
        )
        tip = (
            "Fallback timer — fires if the STT end-of-speech signal "
            "is not received within this many seconds of silence."
            if checked else
            "How long to wait after last word before auto-sending."
        )
        self.silence_threshold.setToolTip(tip)

    # ── STT provider change ────────────────────────────────────────────────────

    def _on_stt_provider_changed(self, idx: int):                      # ← CHANGED
        """
        idx 0 → Deepgram        (show DG model section, hide OAI section)
        idx 1 → OpenAI Realtime (hide DG model section, show OAI section)
        """
        notes = [
            "Deepgram: real-time WebSocket streaming — words appear as spoken, "
            "end-of-turn events for Smart Answering.",
            "OpenAI Realtime: WebSocket with server-side VAD — "
            "no hallucinations on silence, streaming transcript deltas.",
        ]
        self._stt_note.setText(notes[min(idx, len(notes) - 1)])

        is_deepgram = (idx == 0)
        is_openai   = (idx == 1)                                        # ← NEW

        # Deepgram model sub-section
        self._dg_model_section.setVisible(is_deepgram)
        self.deepgram_model.setVisible(is_deepgram)
        self._dg_model_note.setVisible(is_deepgram)

        # OpenAI Realtime model sub-section                             # ← NEW block
        self._oai_model_section.setVisible(is_openai)
        self.openai_stt_model.setVisible(is_openai)
        self._oai_model_note.setVisible(is_openai)

        # Update Smart Answering tooltip to reflect active provider
        if hasattr(self, "smart_answering"):
            if is_openai:
                self.smart_answering.setToolTip(
                    "OpenAI Realtime: dispatches immediately when "
                    "'transcription.completed' fires — server VAD has "
                    "already confirmed end of speech."
                )
            else:
                self.smart_answering.setToolTip("")

    # ── Tab: Overlay ───────────────────────────────────────────────────────────

    def _tab_overlay(self) -> QWidget:
        w, layout, self._overlay_inner = self._scrollable_tab("overlay_inner")

        layout.addWidget(_section("Overlay Opacity"))
        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_label = QLabel("93%")
        self.opacity_label.setObjectName("value_label")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%")
        )
        opacity_row.addWidget(self.opacity_slider)
        opacity_row.addWidget(self.opacity_label)
        layout.addLayout(opacity_row)
        layout.addWidget(_note("Applied immediately after saving."))

        layout.addStretch()
        return w

    # ── Tab: Capture ───────────────────────────────────────────────────────────

    def _tab_capture(self) -> QWidget:
        w, layout, self._capture_inner = self._scrollable_tab("capture_inner")

        layout.addWidget(_section("Capture Region"))

        self._region_label = QLabel("Full screen (no region set)")
        self._region_label.setObjectName("note_label")
        layout.addWidget(self._region_label)

        region_row = QHBoxLayout()
        self._btn_set_region = QPushButton("🎯  Select Region")
        self._btn_set_region.setObjectName("primary")
        self._btn_set_region.clicked.connect(self._select_region)
        region_row.addWidget(self._btn_set_region)

        self._btn_clear_region = QPushButton("✕  Clear Region")
        self._btn_clear_region.clicked.connect(self._clear_region)
        region_row.addWidget(self._btn_clear_region)
        region_row.addStretch()
        layout.addLayout(region_row)

        layout.addWidget(_note(
            "Select only the coding area — 75% fewer pixels → "
            "faster encoding and lower API cost."
        ))

        layout.addWidget(_sep())

        layout.addWidget(_section("Auto Capture"))
        self.auto_capture = QCheckBox("Enable automatic screenshot capture")
        layout.addWidget(self.auto_capture)

        layout.addWidget(_section("Capture Interval  (seconds)"))
        interval_row = QHBoxLayout()
        self.capture_interval = QSpinBox()
        self.capture_interval.setRange(2, 60)
        self.capture_interval.setFixedWidth(100)
        interval_row.addWidget(self.capture_interval)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        layout.addWidget(_sep())

        layout.addWidget(_section("Response Cache"))
        self.use_cache = QCheckBox(
            "Cache identical screenshots (instant repeat answers)"
        )
        layout.addWidget(self.use_cache)
        layout.addWidget(_note(
            "Same screenshot within 30 minutes returns the cached "
            "answer instantly without an API call."
        ))

        cache_row = QHBoxLayout()
        btn_clear_cache = QPushButton("🗑  Clear Cache Now")
        btn_clear_cache.clicked.connect(self._clear_cache)
        cache_row.addWidget(btn_clear_cache)
        cache_row.addStretch()
        layout.addLayout(cache_row)

        layout.addWidget(_sep())

        layout.addWidget(_section("Prompt Caching  (Anthropic Only)"))
        self.use_prompt_cache = QCheckBox("Enable Anthropic prompt caching")
        layout.addWidget(self.use_prompt_cache)
        layout.addWidget(_note(
            "Caches your system prompt (resume + JD) at Anthropic's "
            "servers for 5 minutes. 2nd+ call is ~3× faster and "
            "90% cheaper. Only applies to Claude models."
        ))

        layout.addWidget(_sep())

        layout.addWidget(_section("Screenshot Quality"))
        layout.addWidget(_note("Max screenshot width sent to AI:"))

        width_row = QHBoxLayout()
        self.image_max_width = QComboBox()
        self.image_max_width.addItems([
            "640px   (fastest, lower quality)",
            "1024px  (fast, good quality)",
            "1280px  (recommended — sweet spot)",
            "1920px  (slow, highest quality)",
        ])
        width_row.addWidget(self.image_max_width)
        width_row.addStretch()
        layout.addLayout(width_row)
        layout.addWidget(_note(
            "1280px is the sweet spot for Claude Vision — "
            "32% smaller than 1920px with no quality loss for code."
        ))

        layout.addWidget(_sep())

        layout.addWidget(_section("Connection Optimisation"))
        self.use_http2 = QCheckBox(
            "Use HTTP/2 connection pooling (recommended)"
        )
        layout.addWidget(self.use_http2)
        layout.addWidget(_note(
            "Keeps a persistent connection to the API — saves "
            "~100–150 ms per call by reusing TCP/TLS handshake. "
            "Requires httpx package."
        ))

        layout.addStretch()

        self._update_region_label()
        return w

    # ── Footer ─────────────────────────────────────────────────────────────────

    def _build_footer(self) -> QWidget:
        self._footer_widget = QWidget()
        self._footer_widget.setObjectName("settings_footer")

        fl = QHBoxLayout(self._footer_widget)
        fl.setContentsMargins(20, 12, 20, 12)

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._reset)
        fl.addWidget(reset_btn)
        fl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        fl.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        fl.addWidget(save_btn)

        return self._footer_widget

    # ── Scrollable tab helper ──────────────────────────────────────────────────

    def _scrollable_tab(self, inner_name: str):
        outer = QWidget()
        outer.setObjectName("tab_outer")

        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setObjectName("tab_scroll")

        inner = QWidget()
        inner.setObjectName(inner_name)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        scroll.setWidget(inner)
        ol.addWidget(scroll)

        return outer, layout, inner

    # ── Theme ──────────────────────────────────────────────────────────────────

    def _refresh_theme(self):
        t = th.current()

        self.setStyleSheet(th.make_stylesheet(t) + f"""
            QTabWidget#main_tabs::pane {{
                border: 1px solid {t['border']};
                border-radius: 8px;
                background: {t['bg2']};
            }}
            QTabBar::tab {{
                background: {t['bg3']};
                color: {t['text3']};
                padding: 8px 16px;
                border: none;
                font-size: 12px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {t['bg2']};
                color: {t['text']};
                border-bottom: 2px solid {t['accent']};
            }}
            QLabel#section {{
                color: {t['text3']};
                font-size: 11px;
                letter-spacing: 1px;
                font-weight: 600;
                padding-top: 8px;
                background: transparent;
            }}
            QLabel#note_label {{
                color: {t['text3']};
                font-size: 11px;
                background: transparent;
            }}
            QLabel#value_label {{
                color: {t['accent']};
                font-size: 12px;
                min-width: 42px;
                background: transparent;
            }}
        """)

        self._title_bar_widget.setStyleSheet(f"""
            QWidget#settings_title_bar {{
                background: {t['bg']};
                border-bottom: 1px solid {t['border']};
            }}
        """)

        for lbl in self._title_bar_widget.findChildren(QLabel):
            if lbl.objectName() == "settings_title_lbl":
                lbl.setStyleSheet(
                    f"color:{t['text']}; font-size:14px; font-weight:600;"
                    f"background:transparent; border:none;"
                )

        self._theme_btn.setStyleSheet(th.theme_btn_style(t))
        self._theme_btn.setText("☀" if th.is_dark() else "🌙")

        for btn in self._title_bar_widget.findChildren(QPushButton):
            if btn.objectName() == "settings_close_btn":
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; border: none;
                        color: {t['text3']}; font-size: 14px;
                    }}
                    QPushButton:hover {{ color: {t['danger']}; }}
                """)

        self._footer_widget.setStyleSheet(f"""
            QWidget#settings_footer {{
                background: {t['bg']};
                border-top: 1px solid {t['border']};
            }}
        """)

        for inner in [
            self._account_inner, self._models_inner,
            self._audio_inner,   self._overlay_inner,
            self._capture_inner,
        ]:
            inner.setStyleSheet(f"background: {t['bg2']};")

        # Login wall styling
        self._stack.widget(0).setStyleSheet(f"background: {t['bg2']};")
        if hasattr(self, "_wall_btn"):
            for lbl in self._stack.widget(0).findChildren(QLabel):
                n = lbl.objectName()
                if n == "wall_icon":
                    lbl.setStyleSheet(f"color:{t['accent']}; font-size:42px; background:transparent;")
                elif n == "wall_title":
                    lbl.setStyleSheet(f"color:{t['text']}; font-size:16px; font-weight:700; background:transparent;")
                elif n == "wall_desc":
                    lbl.setStyleSheet(f"color:{t['text3']}; font-size:12px; background:transparent;")

    def _toggle_theme(self):
        th.toggle()
        self._refresh_theme()

    # ── Region capture helpers ─────────────────────────────────────────────────

    def _select_region(self):
        self.hide()
        QTimer.singleShot(300, self._open_selector)

    def _open_selector(self):
        from capture.region_selector import RegionSelector
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.cancelled.connect(self.show)
        self._selector.show()

    def _on_region_selected(self, x: int, y: int, w: int, h: int):
        from capture.screenshot import save_region
        save_region(x, y, w, h)
        self._update_region_label()
        self.show()

    def _clear_region(self):
        from capture.screenshot import clear_region
        clear_region()
        self._update_region_label()

    def _update_region_label(self):
        from capture.screenshot import get_saved_region
        region = get_saved_region()
        if region and isinstance(region, dict):
            self._region_label.setText(
                f"✓ Region: {region['width']}×{region['height']} "
                f"at ({region['x']}, {region['y']})"
            )
        else:
            self._region_label.setText("Full screen (no region set)")

    def _clear_cache(self):
        try:
            from llm.client import client as llm_client
            llm_client.clear_cache()
            original = self._region_label.text()
            self._region_label.setText("✓ Response cache cleared!")
            QTimer.singleShot(
                2000,
                lambda: self._region_label.setText(original)
            )
        except Exception as e:
            print(f"[settings] Cache clear failed: {e}")

    # ── Mode label helper ──────────────────────────────────────────────────────

    def _update_mode_label(self):
        """No-op kept for compatibility (mode label replaced by account status)."""
        pass

    def _open_url(self, url: str):
        """Open URL in default browser."""
        import webbrowser, subprocess
        try:
            webbrowser.open(url)
        except Exception:
            subprocess.Popen(["start", url], shell=True)

    def _open_login(self):
        """Open the GlassNote Cloud login window."""
        from api.login_ui import LoginWindow
        self._login_window = LoginWindow()
        self._login_window.authenticated.connect(self._on_authenticated)
        self._login_window.show()

    def _on_authenticated(self, email: str, plan: str):
        """Called via Qt signal (main thread) when login succeeds."""
        self._user_plan  = plan
        self._user_email = email
        self._show_settings()

    # ── Load values ────────────────────────────────────────────────────────────

    def _load_values(self):
        c = self.cfg

        # Account status
        self._user_plan  = c.get("glassnote_user_plan", "free").strip() or "free"
        self._user_email = c.get("glassnote_user_email", "").strip()
        if hasattr(self, "_acct_status"):
            plan_name = self._user_plan.title()
            if self._user_email:
                self._acct_status.setText(f"✓ Signed in as {self._user_email}  •  Plan: {plan_name}")
            else:
                self._acct_status.setText(f"Plan: {plan_name}")

        # Verify plan from server in background
        self._verify_plan_from_server_v2()

        # API Keys
        self.anthropic_key.setText(c.get("anthropic_api_key", ""))
        self.openai_key.setText(c.get("openai_api_key", ""))
        self.deepgram_key.setText(c.get("deepgram_api_key", ""))

        # Populate plan-filtered model lists BEFORE selecting saved values
        self._populate_plan_models()

        # LLM Models — select saved value (falls back to first if not in list)
        idx = self.anthropic_model.findText(
            c.get("anthropic_model", "claude-haiku-4-5")
        )
        self.anthropic_model.setCurrentIndex(max(0, idx))

        idx = self.openai_model.findText(c.get("openai_model", "gpt-4o-mini"))
        self.openai_model.setCurrentIndex(max(0, idx))

        self.max_tokens.setValue(c.get("max_tokens", 2048))
        self.auto_model_routing.setChecked(c.get("auto_model_routing", True))

        # ── STT Provider  ← CHANGED (removed whisper)
        stt_map = {
            "deepgram":        0,
            "openai_realtime": 1,
        }
        self.stt_provider.setCurrentIndex(
            stt_map.get(c.get("stt_provider", "deepgram"), 0)
        )

        # Deepgram model
        dg_model_map = {
            "flux-general-en": 0,
            "nova-3":          1,
            "nova-2":          2,
        }
        self.deepgram_model.setCurrentIndex(
            dg_model_map.get(c.get("deepgram_model", "flux-general-en"), 0)
        )

        # ── OpenAI Realtime STT model  ← NEW
        oai_stt_map = {
            "gpt-4o-mini-transcribe": 0,
            "gpt-4o-transcribe":      1,
        }
        self.openai_stt_model.setCurrentIndex(
            oai_stt_map.get(c.get("openai_stt_model", "gpt-4o-mini-transcribe"), 0)
        )

        # Fire provider change to show/hide correct sub-sections
        self._on_stt_provider_changed(self.stt_provider.currentIndex())

        # Audio source
        src_map = {"system": 0, "microphone": 1, "both": 2}
        self.audio_source.setCurrentIndex(
            src_map.get(c.get("audio_source", "system"), 0)
        )

        auto_ans = c.get("auto_answer", False)
        self.auto_answer.setChecked(auto_ans)
        self._on_auto_answer_toggled(auto_ans)   # Issue 4b: sync spinbox state on load
        self.silence_threshold.setValue(c.get("silence_threshold", 1.5))

        # Smart Answering
        smart = c.get("smart_answering", False)
        self.smart_answering.setChecked(smart)
        self._on_smart_answering_toggled(smart)

        # Overlay
        opacity_pct = int(c.get("opacity", 0.93) * 100)
        self.opacity_slider.setValue(opacity_pct)
        self.opacity_label.setText(f"{opacity_pct}%")

        # Capture
        self.auto_capture.setChecked(c.get("auto_capture", False))
        self.capture_interval.setValue(c.get("auto_capture_interval", 5))
        self.use_cache.setChecked(c.get("use_response_cache", True))
        self.use_prompt_cache.setChecked(c.get("use_prompt_cache", True))

        width_map = {640: 0, 1024: 1, 1280: 2, 1920: 3}
        self.image_max_width.setCurrentIndex(
            width_map.get(c.get("image_max_width", 1280), 2)
        )

        self.use_http2.setChecked(c.get("use_http2", True))

        self._update_region_label()

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        # ── Maps  ← CHANGED (stt_map: removed whisper, added openai_realtime)
        stt_map   = {0: "deepgram",    1: "openai_realtime"}
        src_map   = {0: "system",      1: "microphone",     2: "both"}
        width_map = {0: 640,           1: 1024,             2: 1280,   3: 1920}
        dg_models = ["flux-general-en", "nova-3", "nova-2"]
        oai_stt_models = [                                               # ← NEW
            "gpt-4o-mini-transcribe",
            "gpt-4o-transcribe",
        ]

        updates = {
            # API keys (only saved if on BYOK plan)
            "anthropic_api_key":     self.anthropic_key.text().strip(),
            "openai_api_key":        self.openai_key.text().strip(),
            "deepgram_api_key":      self.deepgram_key.text().strip(),

            # LLM models
            "anthropic_model":       self.anthropic_model.currentText(),
            "openai_model":          self.openai_model.currentText(),
            "max_tokens":            self.max_tokens.value(),
            "auto_model_routing":    self.auto_model_routing.isChecked(),

            # STT  ← CHANGED
            "stt_provider":          stt_map[self.stt_provider.currentIndex()],
            "deepgram_model":        dg_models[self.deepgram_model.currentIndex()],
            "openai_stt_model":      oai_stt_models[                        # ← NEW
                                         self.openai_stt_model.currentIndex()
                                     ],

            # Audio
            "audio_source":          src_map[self.audio_source.currentIndex()],
            "auto_answer":           self.auto_answer.isChecked(),
            "silence_threshold":     self.silence_threshold.value(),
            "smart_answering":       self.smart_answering.isChecked(),

            # Overlay
            "opacity":               self.opacity_slider.value() / 100,

            # Capture
            "auto_capture":          self.auto_capture.isChecked(),
            "auto_capture_interval": self.capture_interval.value(),
            "use_response_cache":    self.use_cache.isChecked(),
            "use_prompt_cache":      self.use_prompt_cache.isChecked(),
            "image_max_width":       width_map[self.image_max_width.currentIndex()],
            "use_http2":             self.use_http2.isChecked(),
        }

        # Invalidate HTTP/2 pool if the setting changed
        old_http2 = self.cfg.get("use_http2", True)
        if updates["use_http2"] != old_http2:
            try:
                from llm.client import client as llm_client
                llm_client.invalidate_pool()
                print("[settings] HTTP/2 changed — pool reset")
            except Exception:
                pass

        cfg = config.load_config()
        cfg.update(updates)
        config.save_config(cfg)
        self.settings_saved.emit()
        self.close()

    def _reset(self):
        config.reset()
        self.cfg = config.load_config()
        self._user_plan = "free"
        self._load_values()
        self._update_region_label()
        self._apply_plan_restrictions()

    # ── Plan-based UI restrictions ─────────────────────────────────────────────

    def _apply_plan_restrictions(self):
        """Show/hide UI based on user's plan from pricing_config."""
        is_byok = (self._user_plan == "byok")

        # BYOK key fields
        for widget in self._byok_widgets:
            widget.setVisible(is_byok)
        self._byok_upsell.setVisible(not is_byok)

        # Gate plan features
        if hasattr(self, "auto_answer"):
            aa_ok = pricing.is_feature_enabled(self._user_plan, "auto_capture")
            self.auto_answer.setEnabled(aa_ok)
            if not aa_ok:
                self.auto_answer.setChecked(False)
                self.auto_answer.setToolTip("Auto Answer requires Base plan or above.")
            else:
                self.auto_answer.setToolTip("")

        if hasattr(self, "smart_answering"):
            sa_ok = pricing.is_feature_enabled(self._user_plan, "smart_answering")
            self.smart_answering.setEnabled(sa_ok)
            if not sa_ok:
                self.smart_answering.setChecked(False)
                self.smart_answering.setToolTip("Smart Answering requires Base plan or above.")
            else:
                self.smart_answering.setToolTip("")

        if hasattr(self, "use_prompt_cache"):
            pc_ok = pricing.is_feature_enabled(self._user_plan, "prompt_caching")
            self.use_prompt_cache.setEnabled(pc_ok)
            if not pc_ok:
                self.use_prompt_cache.setToolTip("Prompt caching requires Base plan or above.")
            else:
                self.use_prompt_cache.setToolTip("")

        # STT provider gating
        if hasattr(self, "stt_provider"):
            dg_ok  = pricing.is_stt_allowed(self._user_plan, "deepgram")
            oai_ok = pricing.is_stt_allowed(self._user_plan, "openai_realtime")
            model = self.stt_provider.model()
            # Index 0 = Deepgram, index 1 = OpenAI Realtime
            if not dg_ok and self.stt_provider.currentIndex() == 0:
                self.stt_provider.setCurrentIndex(1 if oai_ok else 0)
            if not oai_ok and self.stt_provider.currentIndex() == 1:
                self.stt_provider.setCurrentIndex(0)

        # Refresh model dropdowns
        self._populate_plan_models()


    @staticmethod
    def _get_plan_from_token(token: str) -> str:
        """
        Legacy helper — reads plan from config instead of decoding token.
        Kept for backwards compatibility with any callers.
        Returns the saved plan string.
        """
        try:
            from settings import config as _cfg
            return _cfg.get("glassnote_user_plan", "free") or "free"
        except Exception:
            return "free"

    def _verify_plan_from_server_v2(self):
        """Verify plan with /api/auth/me in background (no raw token/URL needed)."""
        from api.auth_client import auth_client as _ac

        def on_success(data: dict):
            server_plan = data.get("plan", "free")
            if server_plan != self._user_plan:
                self._user_plan = server_plan
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._apply_plan_restrictions)
                print(f"[settings] Plan verified from server: {server_plan}")

        def on_error(msg: str):
            print(f"[settings] Plan verification failed: {msg}")

        _ac.fetch_user_info(on_success=on_success, on_error=on_error)

    def _verify_plan_from_server(self, token: str, api_url: str):
        """Legacy alias — delegates to _verify_plan_from_server_v2."""
        self._verify_plan_from_server_v2()


    # ── Drag ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def showEvent(self, event):
        super().showEvent(event)
        try:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(
                int(self.winId()), 0x00000011
            )
        except Exception:
            pass