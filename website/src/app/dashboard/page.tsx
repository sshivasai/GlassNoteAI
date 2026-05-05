"use client";

import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Download, Zap, Calendar, Shield } from "lucide-react";
import Link from "next/link";
import { DOWNLOAD_URL } from "@/lib/config";

export default function DashboardOverview() {
  const { user } = useAuth();
  if (!user) return null;

  const progressPercentage = user.sessions_limit === -1
    ? 0
    : Math.min((user.sessions_used / user.sessions_limit) * 100, 100);

  // Plan expiry helpers
  const expiresAt = user.plan_expires_at ? new Date(user.plan_expires_at) : null;
  const daysLeft = expiresAt
    ? Math.ceil((expiresAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const expiryWarning = daysLeft !== null && daysLeft <= 5;
  const planLabel = user.plan.charAt(0).toUpperCase() + user.plan.slice(1) +
    (user.byok_enabled ? " (BYOK)" : "");

  return (
    <div className="space-y-8 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">
          Welcome{user.first_name ? `, ${user.first_name}` : ""}!
        </h1>
        <p className="text-[var(--text-secondary)]">Manage your GlassNote account and download the client.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Usage Card */}
        <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-[var(--cyan)]" />
            Current Usage
          </h2>

          <div className="mb-4">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-[var(--text-secondary)]">Sessions used this period</span>
              <span className="font-medium text-white">
                {user.sessions_used} / {user.sessions_limit === -1 ? "∞" : user.sessions_limit}
              </span>
            </div>

            {user.sessions_limit !== -1 && (
              <div className="w-full h-2 bg-[rgba(255,255,255,0.1)] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${progressPercentage >= 90 ? 'bg-red-500' : 'bg-[var(--cyan)]'}`}
                  style={{ width: `${progressPercentage}%` }}
                />
              </div>
            )}
          </div>

          {user.plan === "free" && (
            <div className="mt-6 p-4 rounded-lg bg-[rgba(0,217,255,0.05)] border border-[rgba(0,217,255,0.1)]">
              <p className="text-sm text-[var(--text-secondary)] mb-3">
                Upgrade to Pro for more sessions and managed AI models.
              </p>
              <Link href="/dashboard/billing">
                <Button className="w-full bg-[var(--cyan)] text-black hover:bg-[#00f0ff] font-semibold">
                  Upgrade Plan
                </Button>
              </Link>
            </div>
          )}
        </div>

        {/* Download Card */}
        <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Download className="w-5 h-5 text-[var(--lime)]" />
            Download GlassNote
          </h2>

          <p className="text-sm text-[var(--text-secondary)] mb-6">
            Get the latest version of the GlassNote Windows client.
          </p>

          <div className="space-y-3">
            <a href={DOWNLOAD_URL} download className="block w-full">
              <Button className="w-full justify-between bg-[var(--cyan)] text-white hover:opacity-90">
                <span className="flex items-center gap-2">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.951-1.801" />
                  </svg>
                  Download for Windows (x64)
                </span>
                <Download className="w-4 h-4" />
              </Button>
            </a>
            <p className="text-xs text-center text-[var(--text-muted)]">Requires Windows 10 or later</p>
          </div>
        </div>
      </div>

      {/* Quick Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <p className="text-xs text-[var(--text-muted)] mb-1 uppercase tracking-wider flex items-center gap-1">
            <Shield className="w-3 h-3" /> Current Plan
          </p>
          <p className="text-xl font-bold text-white capitalize">{planLabel}</p>
        </div>
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
          <p className="text-xs text-[var(--text-muted)] mb-1 uppercase tracking-wider">Email Verified</p>
          <p className="text-xl font-bold text-emerald-400">{user.is_verified ? "✓ Yes" : "✗ No"}</p>
        </div>
        <div className={`p-5 rounded-xl border bg-[var(--bg-card)] ${expiryWarning ? "border-red-500/50" : "border-[var(--border)]"
          }`}>
          <p className="text-xs text-[var(--text-muted)] mb-1 uppercase tracking-wider flex items-center gap-1">
            <Calendar className="w-3 h-3" /> Plan Expires
          </p>
          {user.plan === "free" ? (
            <p className="text-xl font-bold text-[var(--text-muted)]">No expiry</p>
          ) : expiresAt ? (
            <>
              <p className={`text-xl font-bold ${expiryWarning ? "text-red-400" : "text-white"}`}>
                {daysLeft}d left
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {expiresAt.toLocaleDateString()}
              </p>
              {expiryWarning && (
                <Link href="/dashboard/billing">
                  <span className="text-xs text-red-400 underline cursor-pointer">Renew now →</span>
                </Link>
              )}
            </>
          ) : (
            <p className="text-xl font-bold text-[var(--text-muted)]">—</p>
          )}
        </div>
      </div>

      <style>{`
        .animate-fade-in { animation: fadeIn 0.5s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
      `}</style>
    </div>
  );
}
