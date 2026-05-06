"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth-context";
import { fetchApi, setToken } from "@/lib/api";
import { X, Loader2, ArrowLeft } from "lucide-react";

/* ─── Toast notification ──────────────────────────────────────────────── */
function Toast({ message, type, onClose }: { message: string; type: "error" | "success" | "info"; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 5000);
    return () => clearTimeout(t);
  }, [onClose]);

  const colors = {
    error: "bg-red-500/10 border-red-500/30 text-red-400",
    success: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    info: "bg-blue-500/10 border-blue-500/30 text-blue-400",
  };

  return (
    <div className={`p-3 rounded-lg border text-sm text-center animate-fade-in ${colors[type]}`}>
      {message}
    </div>
  );
}

/* ─── Google button ───────────────────────────────────────────────────── */
function GoogleButton({ onSuccess }: { onSuccess: (credential: string) => void }) {
  const btnRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Load Google Identity Services script
    if (document.getElementById("gsi-script")) {
      setReady(true);
      return;
    }
    const script = document.createElement("script");
    script.id = "gsi-script";
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => setReady(true);
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!ready || !btnRef.current) return;
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) return;

    // Clear any existing content
    if (btnRef.current) {
      btnRef.current.innerHTML = '';
    }

    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).google?.accounts?.id?.initialize({
        client_id: clientId,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        callback: (response: any) => {
          if (response.credential) onSuccess(response.credential);
        },
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).google?.accounts?.id?.renderButton(btnRef.current, {
        type: "standard",
        theme: "filled_black",
        size: "large",
        width: 380,
        text: "continue_with",
        shape: "pill",
      });
    } catch (e) {
      console.error("Google SSO init error:", e);
    }
  }, [ready, onSuccess]);

  if (!process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID) return null;

  return (
    <>
      <div ref={btnRef} className="flex justify-center min-h-[44px]" />
      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[var(--border)]" />
        </div>
        <div className="relative flex justify-center text-xs">
          <span className="px-3 bg-[var(--bg-card)] text-[var(--text-muted)]">or continue with email</span>
        </div>
      </div>
    </>
  );
}

/* ─── OTP Input ───────────────────────────────────────────────────────── */
function OTPInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  const handleChange = (idx: number, val: string) => {
    if (!/^\d?$/.test(val)) return;
    const arr = value.split("");
    arr[idx] = val;
    const newVal = arr.join("").slice(0, 6);
    onChange(newVal);
    if (val && idx < 5) refs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !value[idx] && idx > 0) {
      refs.current[idx - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    onChange(pasted);
    refs.current[Math.min(pasted.length, 5)]?.focus();
  };

  return (
    <div className="flex gap-2 justify-center" onPaste={handlePaste}>
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={value[i] || ""}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          className="w-11 h-14 text-center text-2xl font-bold rounded-lg border border-[var(--border)] bg-[rgba(255,255,255,0.03)] text-white focus:border-[var(--cyan)] focus:ring-1 focus:ring-[var(--cyan)] outline-none transition-colors"
        />
      ))}
    </div>
  );
}

/* ─── Main Modal ──────────────────────────────────────────────────────── */
export function AuthModal() {
  const router = useRouter();
  const { showAuthModal, closeAuth, authView, setAuthView, refreshUser } = useAuth();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "error" | "success" | "info" } | null>(null);
  const [resendTimer, setResendTimer] = useState(0);

  // Resend cooldown timer
  useEffect(() => {
    if (resendTimer <= 0) return;
    const t = setInterval(() => setResendTimer((v) => v - 1), 1000);
    return () => clearInterval(t);
  }, [resendTimer]);

  if (!showAuthModal) return null;

  const resetForm = () => {
    setFirstName(""); setLastName(""); setEmail(""); setPassword("");
    setOtpCode(""); setOtpEmail(""); setLoading(false); setToast(null);
  };

  const handleClose = () => {
    resetForm();
    closeAuth();
  };

  const switchView = (v: "login" | "signup") => {
    resetForm();
    setAuthView(v);
  };

  /* ── Signup ─────────────────────────────────────────────── */
  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setToast(null);
    try {
      const data = await fetchApi("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName }),
      });
      // Registration returns otp_sent — transition to OTP view
      setOtpEmail(data.email || email);
      setAuthView("otp");
      setResendTimer(60);
      setToast({ message: data.message || "Verification code sent!", type: "success" });
    } catch (err: unknown) {
      const msg = (err as Error).message || "Registration failed.";
      if (msg.toLowerCase().includes("already have an account")) {
        setToast({ message: msg + " Switching to sign in...", type: "info" });
        setTimeout(() => switchView("login"), 2000);
      } else {
        setToast({ message: msg, type: "error" });
      }
    } finally {
      setLoading(false);
    }
  };

  /* ── Login ──────────────────────────────────────────────── */
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setToast(null);
    try {
      const data = await fetchApi("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(data.access_token);
      await refreshUser();
      handleClose();
      router.push("/dashboard");
    } catch (err: unknown) {
      const msg = (err as Error).message || "Login failed.";
      if (msg.toLowerCase().includes("verify your email")) {
        // Backend auto-resent OTP — go to OTP screen
        setOtpEmail(email);
        setAuthView("otp");
        setResendTimer(60);
        setToast({ message: "A verification code has been sent to your email.", type: "info" });
      } else {
        setToast({ message: msg, type: "error" });
      }
    } finally {
      setLoading(false);
    }
  };

  /* ── OTP Verify ─────────────────────────────────────────── */
  const handleVerifyOTP = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (otpCode.length !== 6) {
      setToast({ message: "Please enter the full 6-digit code.", type: "error" });
      return;
    }
    setLoading(true);
    setToast(null);
    try {
      const data = await fetchApi("/auth/verify-otp", {
        method: "POST",
        body: JSON.stringify({ email: otpEmail, code: otpCode }),
      });
      setToken(data.access_token);
      await refreshUser();
      setToast({ message: "Email verified! Redirecting...", type: "success" });
      setTimeout(() => {
        handleClose();
        router.push("/dashboard");
      }, 1000);
    } catch (err: unknown) {
      setToast({ message: (err as Error).message || "Verification failed.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  /* ── Resend OTP ─────────────────────────────────────────── */
  const handleResend = async () => {
    if (resendTimer > 0) return;
    try {
      await fetchApi("/auth/resend-otp", {
        method: "POST",
        body: JSON.stringify({ email: otpEmail }),
      });
      setResendTimer(60);
      setToast({ message: "A new code has been sent to your email.", type: "success" });
    } catch (err: unknown) {
      setToast({ message: (err as Error).message || "Failed to resend code.", type: "error" });
    }
  };

  /* ── Google Auth ────────────────────────────────────────── */
  const handleGoogleSuccess = async (credential: string) => {
    setLoading(true);
    setToast(null);
    try {
      const data = await fetchApi("/auth/google", {
        method: "POST",
        body: JSON.stringify({ credential }),
      });
      setToken(data.access_token);
      await refreshUser();
      handleClose();
      router.push("/dashboard");
    } catch (err: unknown) {
      setToast({ message: (err as Error).message || "Google sign-in failed.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  /* ── Render ─────────────────────────────────────────────── */
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal */}
      <div className="relative w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] backdrop-blur-xl shadow-2xl animate-modal-in overflow-hidden">
        {/* Close button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-[var(--text-muted)] hover:text-white hover:bg-white/5 transition z-10"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="p-8">
          {/* Logo */}
          <div className="text-center mb-6">
            <Logo className="w-10 h-10 rounded-xl mx-auto mb-3" />
            <h2 className="text-2xl font-black text-white">
              {authView === "otp" ? "Verify Your Email" : authView === "signup" ? "Create an account" : "Welcome back"}
            </h2>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {authView === "otp"
                ? `Enter the 6-digit code sent to ${otpEmail}`
                : authView === "signup"
                  ? "Start using GlassNote for free"
                  : "Sign in to your GlassNote account"}
            </p>
          </div>

          {/* Toast */}
          {toast && <div className="mb-4"><Toast {...toast} onClose={() => setToast(null)} /></div>}

          {/* ── OTP View ──────────────────────── */}
          {authView === "otp" && (
            <form onSubmit={handleVerifyOTP} className="space-y-6">
              <OTPInput value={otpCode} onChange={setOtpCode} />

              <Button
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="w-full bg-[var(--cyan)] text-black hover:bg-[#00a8ff] h-11 font-semibold disabled:opacity-40"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Verify & Continue"}
              </Button>

              <div className="text-center text-sm text-[var(--text-secondary)]">
                Didn&apos;t receive the code?{" "}
                {resendTimer > 0 ? (
                  <span className="text-[var(--text-muted)]">Resend in {resendTimer}s</span>
                ) : (
                  <button type="button" onClick={handleResend} className="text-[var(--cyan)] hover:underline font-medium">
                    Resend code
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={() => { setAuthView("signup"); setOtpCode(""); }}
                className="flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-white transition mx-auto"
              >
                <ArrowLeft className="w-3 h-3" /> Back to signup
              </button>
            </form>
          )}

          {/* ── Signup View ───────────────────── */}
          {authView === "signup" && (
            <>
              <GoogleButton key="signup-google" onSuccess={handleGoogleSuccess} />
              <form onSubmit={handleSignup} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="firstName" className="text-xs">First Name</Label>
                    <Input id="firstName" required value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="John" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="lastName" className="text-xs">Last Name</Label>
                    <Input id="lastName" required value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Doe" />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="signupEmail" className="text-xs">Email</Label>
                  <Input id="signupEmail" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="signupPassword" className="text-xs">Password</Label>
                  <Input id="signupPassword" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" minLength={8} />
                  <p className="text-[10px] text-[var(--text-muted)]">Must be at least 8 characters</p>
                </div>

                <Button type="submit" disabled={loading} className="w-full bg-[var(--cyan)] text-black hover:bg-[#00a8ff] h-11 font-semibold">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Create account"}
                </Button>
              </form>

              <p className="mt-5 text-center text-sm text-[var(--text-secondary)]">
                Already have an account?{" "}
                <button onClick={() => switchView("login")} className="text-[var(--cyan)] hover:underline font-medium">Sign in</button>
              </p>
            </>
          )}

          {/* ── Login View ────────────────────── */}
          {authView === "login" && (
            <>
              <GoogleButton key="login-google" onSuccess={handleGoogleSuccess} />
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="loginEmail" className="text-xs">Email</Label>
                  <Input id="loginEmail" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="loginPassword" className="text-xs">Password</Label>
                  <Input id="loginPassword" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
                </div>

                <Button type="submit" disabled={loading} className="w-full bg-[var(--cyan)] text-black hover:bg-[#00a8ff] h-11 font-semibold">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Sign in"}
                </Button>
              </form>

              <p className="mt-5 text-center text-sm text-[var(--text-secondary)]">
                Don&apos;t have an account?{" "}
                <button onClick={() => switchView("signup")} className="text-[var(--cyan)] hover:underline font-medium">Sign up</button>
              </p>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes modalIn {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .animate-modal-in { animation: modalIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        .animate-fade-in { animation: fadeIn 0.3s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
      `}</style>
    </div>
  );
}
