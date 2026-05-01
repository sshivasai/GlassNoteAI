"use client";

import { useState, useEffect } from "react";
import { fetchApi, fetchPublicPricing, Plan } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { CreditCard, Check, ExternalLink, Loader2 } from "lucide-react";

export default function BillingPage() {
  const { user, refreshUser } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [toast, setToast] = useState("");

  useEffect(() => {
    fetchPublicPricing().then(setPlans);
  }, []);

  const handleCheckout = async (planId: string) => {
    setLoading(planId);
    try {
      const data = await fetchApi("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({
          plan: planId,
          success_url: window.location.origin + "/dashboard/billing?success=true",
          cancel_url: window.location.origin + "/dashboard/billing?cancelled=true",
        }),
      });
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err: any) {
      setToast(err.message || "Failed to start checkout.");
    } finally {
      setLoading(null);
    }
  };

  const handleManageBilling = async () => {
    setLoading("portal");
    try {
      const data = await fetchApi("/billing/portal", { method: "POST" });
      if (data.portal_url) {
        window.open(data.portal_url, "_blank");
      }
    } catch (err: any) {
      setToast(err.message || "Failed to open billing portal.");
    } finally {
      setLoading(null);
    }
  };

  // Check URL params for success/cancel feedback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("success") === "true") {
      setToast("✓ Payment successful! Your plan has been upgraded.");
      refreshUser();
      window.history.replaceState({}, "", "/dashboard/billing");
    } else if (params.get("cancelled") === "true") {
      setToast("Checkout was cancelled.");
      window.history.replaceState({}, "", "/dashboard/billing");
    }
  }, [refreshUser]);

  if (!user) return null;

  // FIX: Filter out ALL free plans (free + byok), show only paid plans
  const paidPlans = plans.filter((p) => p.price_type !== "free").sort((a, b) => a.sort_order - b.sort_order);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <CreditCard className="w-8 h-8 text-[var(--cyan)]" />
          Billing
        </h1>
        <p className="text-[var(--text-secondary)]">Manage your subscription and payment method.</p>
      </div>

      {toast && (
        <div className={`p-3 rounded-lg border text-sm text-center ${toast.startsWith("✓") ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400" : "bg-yellow-500/10 border-yellow-500/30 text-yellow-400"}`}>
          {toast}
        </div>
      )}

      {/* Current Plan */}
      <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-1">Current Plan</p>
            <p className="text-2xl font-bold text-white capitalize">{user.plan}</p>
          </div>
          {user.plan !== "free" && (
            <Button
              variant="outline"
              onClick={handleManageBilling}
              disabled={loading === "portal"}
              className="border-[var(--border)] text-[var(--text-secondary)] hover:text-white"
            >
              {loading === "portal" ? <Loader2 className="w-4 h-4 animate-spin" /> : <><ExternalLink className="w-4 h-4 mr-2" />Manage Billing</>}
            </Button>
          )}
        </div>
        {user.plan !== "free" && (
          <p className="text-sm text-[var(--text-muted)] mt-2">
            Use the billing portal to update your payment method, view invoices, or cancel your subscription.
          </p>
        )}
      </div>

      {/* Plan Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {paidPlans.map((plan) => {
          const isCurrent = user.plan === plan.id;
          return (
            <div
              key={plan.id}
              className={`p-5 rounded-xl border transition-colors ${
                isCurrent
                  ? "border-[var(--cyan)] bg-[rgba(0,217,255,0.05)]"
                  : "border-[var(--border)] bg-[var(--bg-card)] hover:border-[var(--border-glow)]"
              }`}
            >
              <h3 className="text-lg font-bold text-white mb-1">{plan.display_name}</h3>
              <p className="text-2xl font-black text-white mb-1">{plan.price_display}</p>
              <p className="text-xs text-[var(--text-muted)] mb-4">{plan.tagline}</p>

              <ul className="space-y-2 mb-5 text-sm">
                <li className="flex items-center gap-2 text-[var(--text-secondary)]">
                  <Check className="w-4 h-4 text-[var(--lime)]" />
                  {plan.sessions_per_month === -1 ? "Unlimited" : plan.sessions_per_month} sessions/mo
                </li>
                <li className="flex items-center gap-2 text-[var(--text-secondary)]">
                  <Check className="w-4 h-4 text-[var(--lime)]" />
                  {plan.session_duration_min === 0 ? "Unlimited" : `${plan.session_duration_min} min`} per session
                </li>
                <li className="flex items-center gap-2 text-[var(--text-secondary)]">
                  <Check className="w-4 h-4 text-[var(--lime)]" />
                  {plan.allowed_models.length} AI models
                </li>
              </ul>

              {isCurrent ? (
                <Button disabled className="w-full bg-[var(--cyan)]/20 text-[var(--cyan)] cursor-default">
                  Current Plan
                </Button>
              ) : (
                <Button
                  onClick={() => handleCheckout(plan.id)}
                  disabled={!!loading}
                  className="w-full bg-[var(--cyan)] text-black hover:bg-[#00a8ff] font-semibold"
                >
                  {loading === plan.id ? <Loader2 className="w-4 h-4 animate-spin" /> : `Upgrade to ${plan.display_name}`}
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
