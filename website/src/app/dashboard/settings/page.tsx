"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchApi, removeToken } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Settings, Loader2, Trash2, Shield } from "lucide-react";

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
    </div>
  );
}
