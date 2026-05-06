"""
api/login_ui.py — GlassNote Cloud authentication dialog.
Thread-safe via internal pyqtSignals (not QTimer.singleShot from threads).
"""
import os, re, sys, threading, webbrowser, subprocess


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a bundled resource.

    Works both when running from source and when packaged by PyInstaller.
    PyInstaller extracts files to sys._MEIPASS at runtime; without this
    helper, os.path.join(__file__) traversal breaks in the .exe because
    the directory structure inside _MEIPASS differs from the source tree.
    """
    if hasattr(sys, "_MEIPASS"):
        # Running inside a PyInstaller .exe — files land at _MEIPASS root
        return os.path.join(sys._MEIPASS, relative_path)
    # Running from source — files are at the GUI/ root (one level above api/)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), relative_path)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QStackedWidget, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QFont, QPixmap, QIcon

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.auth_client import auth_client
from settings import config
from utils import theme as th

LOGO_PATH    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logo.png")
WEBSITE_URL  = "https://glassnoteai.com"
DASHBOARD_URL = "https://glassnoteai.com/dashboard"

def _api_url() -> str:
    url = config.get("glassnote_api_url", "http://localhost:8000") or "http://localhost:8000"
    return url.rstrip("/")

_DARK = {
    "win_bg":"#090b10","title_bg":"#10141d","title_border":"#273041",
    "text":"#f4f7fb","text2":"#aab6c8","text3":"#738095",
    "accent":"#38bdf8","accent_hover":"#0ea5e9",
    "accent_dim":"rgba(56,189,248,0.10)","accent_brd":"rgba(56,189,248,0.34)",
    "danger":"#fb7185","success":"#34d399","warning":"#fbbf24",
    "border":"#273041","input_bg":"#151b26","input_brd":"#2b3648",
    "google_bg":"#111827","google_brd":"#273041",
}
_LIGHT = {
    "win_bg":"#f7f9fc","title_bg":"#ffffff","title_border":"#d8e0ea",
    "text":"#111827","text2":"#526071","text3":"#8995a6",
    "accent":"#0284c7","accent_hover":"#0369a1",
    "accent_dim":"rgba(2,132,199,0.08)","accent_brd":"rgba(2,132,199,0.26)",
    "danger":"#e11d48","success":"#059669","warning":"#b7791f",
    "border":"#d8e0ea","input_bg":"#ffffff","input_brd":"#cbd5e1",
    "google_bg":"#ffffff","google_brd":"#d8e0ea",
}
def _t(): return _DARK if th.is_dark() else _LIGHT
def _sep():
    f = QFrame(); f.setObjectName("sep"); f.setFrameShape(QFrame.Shape.HLine); return f


class LoginWindow(QWidget):
    """Login/Register — uses internal signals to safely bridge background threads."""
    authenticated = pyqtSignal(str, str)   # email, plan

    # Internal thread→UI bridge signals
    _sig_success = pyqtSignal(dict)
    _sig_error   = pyqtSignal(str)
    _sig_google_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._mode = "login"
        self._loading_timer = None
        self._loading_dots  = 0

        url = _api_url()
        auth_client.configure(url)

        # Connect internal signals (always on main thread)
        self._sig_success.connect(self._handle_success)
        self._sig_error.connect(self._handle_error)
        self._sig_google_url.connect(self._launch_google_browser)

        self._build_ui()
        self._apply_theme()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("GlassNote - Sign In")
        self.setFixedWidth(440)
        self.setFont(QFont("Segoe UI", 11))

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar
        self._title_bar = QWidget(); self._title_bar.setObjectName("title_bar")
        self._title_bar.setFixedHeight(56)
        tl = QHBoxLayout(self._title_bar); tl.setContentsMargins(16, 0, 10, 0)

        # Logo
        logo_lbl = QLabel()
        px = QPixmap(LOGO_PATH)
        if not px.isNull():
            logo_lbl.setPixmap(px.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        else:
            logo_lbl.setText("◈"); logo_lbl.setObjectName("icon_label")
        tl.addWidget(logo_lbl)

        self._title_lbl = QLabel("Sign In to GlassNote")
        self._title_lbl.setObjectName("title_label")
        tl.addWidget(self._title_lbl); tl.addStretch()

        close_btn = QPushButton("×"); close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        tl.addWidget(close_btn); self._close_btn = close_btn
        root.addWidget(self._title_bar)

        # ── Body
        self._body = QWidget(); self._body.setObjectName("body")
        bl = QVBoxLayout(self._body); bl.setContentsMargins(28, 18, 28, 24); bl.setSpacing(10)

        # Google button
        self._btn_google = QPushButton("  Continue with Google")
        self._btn_google.setObjectName("google_btn")
        self._btn_google.setCursor(Qt.CursorShape.PointingHandCursor)
        # Use resource_path() so the icon resolves correctly in both source
        # and PyInstaller .exe (where sys._MEIPASS is the extraction root).
        _g_px = QPixmap(resource_path("icons8-google-96.png"))
        if not _g_px.isNull():
            self._btn_google.setIcon(QIcon(_g_px))
        self._btn_google.clicked.connect(self._on_google_signin)
        bl.addWidget(self._btn_google)

        # Divider
        dr = QHBoxLayout()
        dl = QFrame(); dl.setFrameShape(QFrame.Shape.HLine)
        dlbl = QLabel("or"); dlbl.setObjectName("div_label")
        dlbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dr2 = QFrame(); dr2.setFrameShape(QFrame.Shape.HLine)
        dr.addWidget(dl); dr.addWidget(dlbl); dr.addWidget(dr2)
        bl.addLayout(dr)

        # Email
        el = QLabel("EMAIL"); el.setObjectName("field_label"); bl.addWidget(el)
        self._email = QLineEdit(); self._email.setPlaceholderText("you@example.com")
        self._email.returnPressed.connect(self._on_submit); bl.addWidget(self._email)

        # Password
        pl = QLabel("PASSWORD"); pl.setObjectName("field_label"); bl.addWidget(pl)
        self._password = QLineEdit(); self._password.setPlaceholderText("••••••••")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.returnPressed.connect(self._on_submit); bl.addWidget(self._password)

        # Confirm (register only)
        self._confirm_lbl = QLabel("CONFIRM PASSWORD"); self._confirm_lbl.setObjectName("field_label")
        bl.addWidget(self._confirm_lbl)
        self._confirm_pwd = QLineEdit(); self._confirm_pwd.setPlaceholderText("••••••••")
        self._confirm_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        bl.addWidget(self._confirm_pwd)
        self._confirm_lbl.hide(); self._confirm_pwd.hide()

        # Status
        self._status = QLabel(""); self._status.setObjectName("status_label")
        self._status.setWordWrap(True); bl.addWidget(self._status)

        # Submit
        self._btn_submit = QPushButton("Sign In"); self._btn_submit.setObjectName("primary")
        self._btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_submit.clicked.connect(self._on_submit); bl.addWidget(self._btn_submit)

        # Toggle
        self._toggle_lbl = QLabel(""); self._toggle_lbl.setObjectName("toggle_label")
        self._toggle_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_lbl.mousePressEvent = lambda _: self._toggle_mode()
        bl.addWidget(self._toggle_lbl)
        self._update_toggle_text()

        # Dashboard note
        dash_lbl = QLabel(
            "Track usage & manage billing at "
            f"<a href='{DASHBOARD_URL}' style='color:#38bdf8;'>glassnote.ai/dashboard</a>"
        )
        dash_lbl.setObjectName("dash_label")
        dash_lbl.setOpenExternalLinks(True)
        dash_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(dash_lbl)

        root.addWidget(self._body)

    # ── Google OAuth ───────────────────────────────────────────────────────────

    def _on_google_signin(self):
        self._set_loading(True, "google")
        self._show_status("Fetching Google sign-in URL…", "neutral")
        url = _api_url()
        auth_client.configure(url)
        auth_client.get_google_auth_url(
            on_success=lambda u: self._sig_google_url.emit(u),  # safe cross-thread
            on_error=lambda msg: self._sig_error.emit(msg),
        )

    def _launch_google_browser(self, url: str):
        """
        Start the local OAuth callback server FIRST, then open the browser.

        The server must be bound and listening before the browser is opened,
        otherwise the OAuth redirect arrives before the server is ready and
        the user sees ERR_CONNECTION_REFUSED.  A threading.Event is used to
        signal readiness from the listener thread back to this method.
        """
        self._show_status("🌐 Complete sign-in in your browser…", "neutral")

        # Event set by the listener thread once the server socket is bound
        server_ready = threading.Event()

        listener = threading.Thread(
            target=self._listen_for_google_callback,
            args=(server_ready,),
            daemon=True, name="google-cb"
        )
        listener.start()

        # Wait up to 3 s for the server to bind before opening the browser.
        # On a healthy machine this takes < 10 ms; 3 s is a generous safety net.
        if not server_ready.wait(timeout=3.0):
            self._sig_error.emit(
                "Could not start local OAuth server. Port 9999 may be in use."
            )
            return

        try:
            webbrowser.open(url)
        except Exception:
            try:
                subprocess.Popen(["start", url], shell=True)
            except Exception as e:
                self._sig_error.emit(f"Could not open browser: {e}")

    def _listen_for_google_callback(self, server_ready: threading.Event = None):
        """
        Bind a local HTTP server on port 9999, signal readiness, then wait
        for the Google OAuth redirect to deliver the authorization code.

        The server_ready Event (if provided) is set immediately after the
        socket is successfully bound so the caller can open the browser only
        once the server is actually listening.

        http.server must NOT be in the PyInstaller excludes list — it is
        required here.  See glassnote.spec.
        """
        import http.server, urllib.parse
        code_holder = [None]

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                p = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(p.query)
                code  = q.get("code",  [None])[0]
                error = q.get("error", [None])[0]
                code_holder[0] = f"ERR:{error}" if error else (code or "")
                html = b"<html><body style='background:#090b10;color:#f4f7fb;font-family:sans-serif;text-align:center;padding-top:80px'><h2 style='color:#38bdf8'>GlassNote</h2><p>Sign-in complete! You can close this tab.</p></body></html>"
                self.send_response(200); self.send_header("Content-type","text/html"); self.end_headers()
                self.wfile.write(html); self.server.should_stop = True

        try:
            srv = http.server.HTTPServer(("localhost", 9999), _H)
        except OSError:
            self._sig_error.emit("Port 9999 is in use. Close other apps and retry.")
            if server_ready is not None:
                server_ready.set()   # unblock caller so it doesn't hang
            return

        # ── Server socket is now bound and listening ──────────────────────────
        # Signal the caller BEFORE entering the request loop so the browser
        # is opened only after we are guaranteed to be accepting connections.
        if server_ready is not None:
            server_ready.set()

        srv.should_stop = False; srv.timeout = 0.5
        for _ in range(360):
            srv.handle_request()
            if srv.should_stop: break
        srv.server_close()

        code = code_holder[0] or ""
        if code and not code.startswith("ERR:"):
            auth_client.google_auth_with_code(
                code=code,
                on_success=lambda d: self._sig_success.emit(d),
                on_error=lambda m: self._sig_error.emit(m),
            )
        elif code.startswith("ERR:"):
            self._sig_error.emit("Google sign-in was cancelled.")
        else:
            self._sig_error.emit("Google sign-in timed out. Please try again.")

    # ── Email/password ─────────────────────────────────────────────────────────

    def _toggle_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        if self._mode == "register":
            self._title_lbl.setText("Create GlassNote Account")
            self._btn_submit.setText("Create Account")
            self._confirm_lbl.show(); self._confirm_pwd.show()
        else:
            self._title_lbl.setText("Sign In to GlassNote")
            self._btn_submit.setText("Sign In")
            self._confirm_lbl.hide(); self._confirm_pwd.hide()
        self._status.setText(""); self._update_toggle_text(); self.adjustSize()

    def _update_toggle_text(self):
        if self._mode == "login":
            self._toggle_lbl.setText("Don't have an account?  <b>Create one →</b>")
        else:
            self._toggle_lbl.setText("Already have an account?  <b>Sign in →</b>")

    def _on_submit(self):
        email = self._email.text().strip()
        pw    = self._password.text()
        if not email or not pw:
            self._show_status("❌ Please enter both email and password.", "error"); return
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            self._show_status("❌ Invalid email address.", "error"); return
        if len(pw) < 8:
            self._show_status("❌ Password must be at least 8 characters.", "error"); return
        if self._mode == "register" and pw != self._confirm_pwd.text():
            self._show_status("❌ Passwords don't match.", "error"); return

        # Re-read URL each time (user may have updated config)
        auth_client.configure(_api_url())
        self._set_loading(True, "submit")

        # Use lambda to emit signal — safe from background thread
        ok  = lambda d: self._sig_success.emit(d)
        err = lambda m: self._sig_error.emit(m)

        if self._mode == "login":
            auth_client.login(email, pw, on_success=ok, on_error=err)
        else:
            auth_client.register(email, pw, on_success=ok, on_error=err)

    # ── Handle results (always on main thread via signals) ─────────────────────

    def _handle_success(self, user_info: dict):
        self._set_loading(False)
        email     = user_info.get("email", "")
        plan      = user_info.get("plan", "free")
        needs_otp = user_info.get("needs_otp", False)

        if needs_otp:
            self._show_otp_panel(email); return

        cfg = config.load_config()
        cfg["glassnote_api_url"] = _api_url()
        config.save_config(cfg)

        self._show_status(f"✅ Signed in as {email}  •  Plan: {plan.title()}", "success")
        self._btn_submit.setText("✓ Connected")
        self.authenticated.emit(email, plan)
        QTimer.singleShot(1400, self.close)

    def _handle_error(self, message: str):
        self._set_loading(False)
        msg = message.lower()
        if "verify" in msg or "not verified" in msg:
            self._show_status("⚠️ Check your email for a verification code.", "warning")
            email = self._email.text().strip()
            if email:
                QTimer.singleShot(400, lambda: self._show_otp_panel(email))
        elif "invalid email or password" in msg:
            self._show_status("❌ Incorrect email or password.", "error")
        elif "already exists" in msg:
            self._show_status("⚠️ Account exists — please sign in instead.", "warning")
        elif "different device" in msg:
            self._show_status("❌ Account linked to another device.\nVisit glassnote.ai to unlink.", "error")
        elif "cannot connect" in msg or "network" in msg or "connect" in msg:
            self._show_status("⚠️ Cannot reach GlassNote server.\nCheck your connection.", "warning")
        elif "timed out" in msg:
            self._show_status("⚠️ Connection timed out. Please try again.", "warning")
        else:
            self._show_status(f"❌ {message}", "error")
        # Restore button text
        self._btn_submit.setText("Sign In" if self._mode == "login" else "Create Account")

    # ── OTP panel ──────────────────────────────────────────────────────────────

    def _show_otp_panel(self, email: str):
        self._title_lbl.setText("Verify Your Email")
        self._btn_google.hide()
        self._email.hide(); self._password.hide()
        self._confirm_lbl.hide(); self._confirm_pwd.hide()

        bl = self._body.layout()
        if not hasattr(self, "_otp_field"):
            od = QLabel(f"A 6-digit code was sent to:\n{email}")
            od.setObjectName("desc_label"); od.setWordWrap(True)
            bl.insertWidget(0, od)
            ol = QLabel("VERIFICATION CODE"); ol.setObjectName("field_label")
            bl.insertWidget(1, ol)
            self._otp_field = QLineEdit()
            self._otp_field.setPlaceholderText("1  2  3  4  5  6")
            self._otp_field.setMaxLength(6)
            self._otp_field.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.insertWidget(2, self._otp_field)
            rl = QLabel("Didn't receive it?  <b>Resend code →</b>")
            rl.setObjectName("toggle_label")
            rl.setCursor(Qt.CursorShape.PointingHandCursor)
            rl.mousePressEvent = lambda _: auth_client.resend_otp(
                email,
                on_success=lambda m: self._sig_success.emit({"_msg": m}),
                on_error=lambda m: self._sig_error.emit(m),
            )
            bl.insertWidget(3, rl)

        t = _t()
        self._otp_field.setStyleSheet(
            f"font-size:28px;font-weight:700;letter-spacing:14px;"
            f"background:{t['input_bg']};border:1.5px solid {t['accent']};"
            f"border-radius:8px;color:{t['text']};padding:10px;"
        )
        self._btn_submit.setText("Verify Code"); self._btn_submit.setEnabled(True)
        try: self._btn_submit.clicked.disconnect()
        except Exception: pass
        self._btn_submit.clicked.connect(lambda: self._on_verify_otp(email))
        self._status.setText(""); self.adjustSize()

    def _on_verify_otp(self, email: str):
        if not hasattr(self, "_otp_field"): return
        code = self._otp_field.text().strip()
        if len(code) != 6 or not code.isdigit():
            self._show_status("❌ Enter the 6-digit code from your email.", "error"); return
        self._set_loading(True, "submit")
        auth_client.verify_otp(
            email=email, code=code,
            on_success=lambda d: self._sig_success.emit(d),
            on_error=lambda m: self._sig_error.emit(m),
        )

    # ── Loading state ──────────────────────────────────────────────────────────

    def _set_loading(self, loading: bool, which: str = "submit"):
        if loading:
            self._btn_submit.setEnabled(False)
            self._btn_google.setEnabled(False)
            self._loading_base = "Opening Google" if which == "google" else "Connecting"
            self._loading_dots = 0
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._tick_loading)
            self._loading_timer.start(400)
        else:
            if self._loading_timer:
                self._loading_timer.stop(); self._loading_timer = None
            self._btn_submit.setEnabled(True)
            self._btn_google.setEnabled(True)
            self._btn_google.setText("  Continue with Google")

    def _tick_loading(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        self._btn_submit.setText(self._loading_base + "." * self._loading_dots)

    # ── Status ─────────────────────────────────────────────────────────────────

    def _show_status(self, msg: str, level: str = "error"):
        t = _t()
        c = {"error":t["danger"],"success":t["success"],"warning":t["warning"],"neutral":t["text2"]}.get(level, t["danger"])
        self._status.setStyleSheet(f"color:{c};font-size:12px;background:transparent;")
        self._status.setText(msg)

    # ── Theme ──────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = _t()
        self.setStyleSheet(f"""
            QWidget#body {{ background:{t['win_bg']}; border-bottom-left-radius:8px; border-bottom-right-radius:8px; }}
            QLabel#field_label {{ color:{t['text3']}; font-size:11px; font-weight:700; letter-spacing:0; background:transparent; }}
            QLabel#desc_label {{ color:{t['text2']}; font-size:12px; background:transparent; }}
            QLabel#status_label {{ font-size:12px; background:transparent; }}
            QLabel#toggle_label {{ color:{t['text2']}; font-size:12px; background:transparent; }}
            QLabel#toggle_label:hover {{ color:{t['accent']}; }}
            QLabel#div_label {{ color:{t['text3']}; font-size:11px; background:transparent; padding:0 8px; }}
            QLabel#dash_label {{ color:{t['text3']}; font-size:11px; background:transparent; }}
            QFrame[frameShape="4"] {{ background:{t['border']}; max-height:1px; border:none; }}
            QLineEdit {{ background:{t['input_bg']}; border:1px solid {t['input_brd']}; border-radius:8px; color:{t['text']}; font-size:13px; padding:9px 12px; }}
            QLineEdit:focus {{ border-color:{t['accent']}; }}
            QLineEdit::placeholder {{ color:{t['text3']}; }}
            QPushButton#primary {{ background:{t['accent']}; color:white; border:none; border-radius:8px; font-size:13px; font-weight:700; padding:10px 22px; min-height:42px; }}
            QPushButton#primary:hover {{ background:{t['accent_hover']}; }}
            QPushButton#primary:disabled {{ background:{t['text3']}; }}
            QPushButton#google_btn {{ background:{t['google_bg']}; color:{t['text']}; border:1px solid {t['google_brd']}; border-radius:8px; font-size:13px; font-weight:600; padding:9px 16px; min-height:42px; }}
            QPushButton#google_btn:hover {{ border-color:{t['accent']}; color:{t['accent']}; background:{t['accent_dim']}; }}
            QPushButton#google_btn:disabled {{ color:{t['text3']}; }}
        """)
        self._title_bar.setStyleSheet(f"""
            QWidget#title_bar {{ background:{t['title_bg']}; border-bottom:1px solid {t['title_border']}; border-top-left-radius:8px; border-top-right-radius:8px; }}
        """)
        self._title_lbl.setStyleSheet(f"color:{t['text']};font-size:15px;font-weight:700;margin-left:6px;border:none;background:transparent;")
        self._close_btn.setStyleSheet(f"""
            QPushButton#close_btn {{ background:transparent; border:1px solid {t['border']}; border-radius:8px; color:{t['text3']}; font-size:13px; font-weight:700; }}
            QPushButton#close_btn:hover {{ background:{t['danger']}; border-color:{t['danger']}; color:white; }}
        """)

    # ── Drag ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def showEvent(self, e):
        super().showEvent(e)
        self.adjustSize()
        try:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x00000011)
        except Exception:
            pass
