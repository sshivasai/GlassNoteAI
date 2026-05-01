"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchApi, removeToken } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Settings, Loader2, Trash2, Shield, CreditCard } from "lucide-react";

export default function SettingsPage() {
  const router = useRouter();
  const { user, refreshUser, logout } = useAuth();

  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName] = useState(user?.last_name || "");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  // Delete account state
  const [showDelete, setShowDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);

  // Plan switching state
  const [switchingPlan, setSwitchingPlan] = useState(false);
  const [showSwitchModal, setShowSwitchModal] = useState(false);
  const [targetPlan, setTargetPlan] = useState<"free" | "byok" | null>(null);

  if (!user) return null;

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setToast(null);
    try {
      await fetchApi("/auth/profile", {
        method: "PUT",
        body: JSON.stringify({ first_name: firstName, last_name: lastName }),
      });
      await refreshUser();
      setToast({ message: "Profile updated successfully.", type: "success" });
    } catch (err: any) {
      setToast({ message: err.message || "Failed to update profile.", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (user.auth_provider === "email" && !deletePassword) {
      setToast({ message: "Please enter your password to confirm.", type: "error" });
      return;
    }
    setDeleting(true);
    setToast(null);
    try {
      await fetchApi("/auth/account", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword }),
      });
      removeToken();
      logout();
      router.push("/");
    } catch (err: any) {
      setToast({ message: err.message || "Failed to delete account.", type: "error" });
    } finally {
      setDeleting(false);
    }
  };

  const handleSwitchPlan = async (plan: "free" | "byok") => {
    setSwitchingPlan(true);
    setToast(null);
    setShowSwitchModal(false); // Close modal
    try {
      await fetchApi("/auth/switch-plan", {
        method: "POST",
        body: JSON.stringify({ plan }),
      });
      await refreshUser();
      setToast({
        message: `Successfully switched to ${plan.toUpperCase()} plan!`,
        type: "success"
      });
    } catch (err: any) {
      setToast({ message: err.message || "Failed to switch plan.", type: "error" });
    } finally {
      setSwitchingPlan(false);
      setTargetPlan(null);
    }
  };

  const openSwitchModal = (plan: "free" | "byok") => {
    setTargetPlan(plan);
    setShowSwitchModal(true);
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <Settings className="w-8 h-8 text-[var(--cyan)]" />
          Settings
        </h1>
        <p className="text-[var(--text-secondary)]">Update your profile and manage your account.</p>
      </div>

      {toast && (
        <div className={`p-3 rounded-lg border text-sm ${toast.type === "success" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-red-500/10 border-red-500/30 text-red-400"}`}>
          {toast.message}
        </div>
      )}

      {/* Profile */}
      <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-[var(--cyan)]" />
          Profile
        </h2>

        <form onSubmit={handleSaveProfile} className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs text-[var(--text-muted)]">Email</Label>
            <Input value={user.email} disabled className="opacity-60 cursor-not-allowed" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="settingsFirstName" className="text-xs">First Name</Label>
              <Input id="settingsFirstName" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="settingsLastName" className="text-xs">Last Name</Label>
              <Input id="settingsLastName" value={lastName} onChange={(e) => setLastName(e.target.value)} />
            </div>
          </div>

          <div className="flex items-center gap-3 text-sm text-[var(--text-muted)]">
            <span>Auth provider:</span>
            <span className="capitalize font-medium text-white">{user.auth_provider}</span>
          </div>

          <Button type="submit" disabled={saving} className="bg-[var(--cyan)] text-black hover:bg-[#00a8ff] font-semibold">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Save Changes"}
          </Button>
        </form>
      </div>

      {/* Plan Switching (Free ↔ BYOK) */}
      {(user.plan === "free" || user.plan === "byok") && (
        <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-[var(--cyan)]" />
            Plan Management
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            {user.plan === "free"
              ? "Switch to BYOK to use your own API keys with unlimited sessions."
              : "Switch back to Free plan if you prefer limited sessions."}
          </p>

          {/* Important Note about Lifetime Sessions */}
          <div className="mb-4 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
            <p className="text-xs text-blue-300">
              ℹ️ <strong>Note:</strong> Free and BYOK plans share the same lifetime session quota.
              You have <strong>{user.sessions_limit - user.sessions_used}</strong> lifetime sessions remaining
              (out of {user.sessions_limit}), regardless of which plan you choose.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="text-sm font-medium text-white mb-1">
                Current Plan: <span className="text-[var(--cyan)] uppercase">{user.plan}</span>
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                {user.plan === "free"
                  ? "5 lifetime sessions, 30 min each"
                  : "Unlimited sessions with your own API keys"}
              </div>
            </div>

            <Button
              onClick={() => openSwitchModal(user.plan === "free" ? "byok" : "free")}
              disabled={switchingPlan}
              className="bg-[var(--cyan)] text-black hover:bg-[#00a8ff] font-semibold"
            >
              {switchingPlan ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                `Switch to ${user.plan === "free" ? "BYOK" : "Free"}`
              )}
            </Button>
          </div>

          {user.plan === "byok" && (
            <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <p className="text-xs text-yellow-400">
                ⚠️ <strong>Important:</strong> Switching to Free limits you to 5 lifetime sessions total.
                Free and BYOK share the same quota, so sessions used on BYOK count toward your Free limit.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Paid Plan Upgrade Link (for Free/BYOK users) */}
      {(user.plan === "free" || user.plan === "byok") && (
        <div className="p-6 rounded-xl border border-[var(--border-glow)] bg-gradient-to-br from-[var(--cyan-dim)] to-[var(--lime-dim)]">
          <h3 className="text-lg font-semibold text-white mb-2">
            Want unlimited sessions without managing API keys?
          </h3>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Upgrade to Base ($29/mo) or Unlimited ($49/mo) for premium features.
          </p>
          <Button
            onClick={() => router.push("/dashboard/billing")}
            className="bg-white text-black hover:bg-gray-100 font-semibold"
          >
            View Paid Plans
          </Button>
        </div>
      )}

      {/* Paid Plan → BYOK Switch (for Base/Unlimited users) */}
      {(user.plan === "base" || user.plan === "unlimited") && (
        <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-[var(--cyan)]" />
            Switch to BYOK (Free)
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            Want to use your own API keys instead of paying monthly? Switch to BYOK for free unlimited sessions.
          </p>

          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-[var(--cyan-dim)] border border-[var(--cyan)]/20">
              <p className="text-xs text-white/80">
                <strong className="text-[var(--cyan)]">BYOK Benefits:</strong><br />
                • Free forever (no monthly charge)<br />
                • Unlimited sessions & duration<br />
                • Use your own Anthropic/OpenAI keys<br />
                • All premium features included
              </p>
            </div>

            <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <p className="text-xs text-yellow-400">
                ⚠️ <strong>Before switching:</strong> You must cancel your {user.plan} subscription
                via the billing page first. Then you can switch to BYOK for free.
              </p>
            </div>

            <Button
              onClick={() => router.push("/dashboard/billing")}
              className="bg-[var(--cyan)] text-black hover:bg-[#00a8ff] font-semibold w-full"
            >
              Go to Billing to Cancel Subscription
            </Button>
          </div>
        </div>
      )}

      {/* Danger Zone */}
      <div className="p-6 rounded-xl border border-red-500/20 bg-[rgba(255,0,0,0.02)]">
        <h2 className="text-lg font-semibold text-red-400 mb-2 flex items-center gap-2">
          <Trash2 className="w-5 h-5" />
          Danger Zone
        </h2>
        <p className="text-sm text-[var(--text-secondary)] mb-4">
          Permanently delete your account and all associated data. This action cannot be undone.
        </p>

        {!showDelete ? (
          <Button
            variant="outline"
            onClick={() => setShowDelete(true)}
            className="border-red-500/30 text-red-400 hover:bg-red-500/10"
          >
            Delete my account
          </Button>
        ) : (
          <div className="space-y-3 p-4 rounded-lg bg-red-500/5 border border-red-500/20">
            <p className="text-sm text-red-400 font-medium">Are you sure? This will delete everything permanently.</p>

            {user.auth_provider === "email" && (
              <div className="space-y-1.5">
                <Label className="text-xs text-red-300">Enter your password to confirm</Label>
                <Input
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  placeholder="Your password"
                  className="border-red-500/30"
                />
              </div>
            )}

            <div className="flex gap-3">
              <Button
                onClick={handleDeleteAccount}
                disabled={deleting}
                className="bg-red-600 text-white hover:bg-red-700 font-semibold"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Yes, delete my account"}
              </Button>
              <Button
                variant="outline"
                onClick={() => { setShowDelete(false); setDeletePassword(""); }}
                className="border-[var(--border)] text-[var(--text-secondary)]"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Plan Switch Confirmation Modal */}
      {showSwitchModal && targetPlan && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--bg-primary)] border border-[var(--border)] rounded-xl shadow-2xl max-w-md w-full p-6 space-y-4">
            {/* Modal Header */}
            <div className="flex items-start gap-3">
              <div className={`p-2 rounded-lg ${
                targetPlan === "free"
                  ? "bg-yellow-500/10"
                  : "bg-[var(--cyan-dim)]"
              }`}>
                <CreditCard className={`w-6 h-6 ${
                  targetPlan === "free"
                    ? "text-yellow-400"
                    : "text-[var(--cyan)]"
                }`} />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-white">
                  Switch to {targetPlan.toUpperCase()} Plan?
                </h3>
                <p className="text-sm text-[var(--text-secondary)] mt-1">
                  {targetPlan === "free"
                    ? "You'll lose unlimited sessions"
                    : "You'll gain unlimited sessions"}
                </p>
              </div>
            </div>

            {/* Modal Content */}
            <div className="space-y-3">
              {targetPlan === "free" ? (
                <>
                  <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                    <p className="text-sm text-yellow-400 font-medium mb-2">
                      ⚠️ You're switching to Free plan
                    </p>
                    <ul className="text-xs text-yellow-300/80 space-y-1">
                      <li>• Quota: Unlimited → 5 lifetime sessions</li>
                      <li>• Duration: Unlimited → 30 min per session</li>
                      <li>• Your API keys will be preserved</li>
                      <li>• You can switch back to BYOK anytime (free)</li>
                    </ul>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 mt-2">
                    <p className="text-xs text-blue-300">
                      ℹ️ <strong>Quota Sharing:</strong> Free and BYOK share the same lifetime quota.
                      Sessions used on BYOK count toward your Free plan limit (and vice versa).
                    </p>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-2">
                    This change is instant and reversible. Your session history remains intact.
                  </p>
                </>
              ) : (
                <>
                  <div className="p-3 rounded-lg bg-[var(--cyan-dim)] border border-[var(--cyan)]/20">
                    <p className="text-sm text-[var(--cyan)] font-medium mb-2">
                      ✨ You're upgrading to BYOK
                    </p>
                    <ul className="text-xs text-white/80 space-y-1">
                      <li>• Quota: 5 lifetime → Unlimited sessions</li>
                      <li>• Duration: 30 min → Unlimited per session</li>
                      <li>• Use your own Anthropic/OpenAI API keys</li>
                      <li>• All premium features enabled</li>
                    </ul>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 mt-2">
                    <p className="text-xs text-blue-300">
                      ℹ️ <strong>Quota Sharing:</strong> Free and BYOK share the same lifetime quota.
                      Sessions used on Free count toward your BYOK limit when you switch back.
                    </p>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-2">
                    You'll need to add your own API keys in Settings → API Keys after switching.
                  </p>
                </>
              )}
            </div>

            {/* Modal Actions */}
            <div className="flex gap-3 pt-2">
              <Button
                onClick={() => handleSwitchPlan(targetPlan)}
                disabled={switchingPlan}
                className={`flex-1 font-semibold ${
                  targetPlan === "free"
                    ? "bg-yellow-500 text-black hover:bg-yellow-600"
                    : "bg-[var(--cyan)] text-black hover:bg-[#00a8ff]"
                }`}
              >
                {switchingPlan ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  `Yes, Switch to ${targetPlan.toUpperCase()}`
                )}
              </Button>
              <Button
                onClick={() => {
                  setShowSwitchModal(false);
                  setTargetPlan(null);
                }}
                disabled={switchingPlan}
                variant="outline"
                className="border-[var(--border)] text-[var(--text-secondary)] hover:bg-white/5"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
