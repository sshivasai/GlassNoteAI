"use client";

import { useState, useEffect } from "react";
import { fetchPublicPricing, Plan } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { CreditCard, Check, Clock } from "lucide-react";

export default function BillingPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);

  useEffect(() => {
    fetchPublicPricing().then(setPlans);
  }, []);

  if (!user) return null;

  // Filter out ALL free plans (free + byok), show only paid plans
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

      {/* Coming Soon Notice */}
      <div className="p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/5 flex items-center gap-3">
        <Clock className="w-5 h-5 text-yellow-400 shrink-0" />
        <p className="text-sm text-yellow-300">
          <span className="font-semibold">Paid plans are coming soon.</span> Online checkout is not yet available. Contact{" "}
          <a href="mailto:support@glassnoteai.com" className="underline hover:text-yellow-200 transition-colors">
            support@glassnoteai.com
          </a>{" "}
          for early access or billing questions.
        </p>
      </div>

      {/* Current Plan */}
      <div className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-1">Current Plan</p>
            <p className="text-2xl font-bold text-white capitalize">{user.plan}</p>
          </div>
          {user.plan !== "free" && (
            <a
              href="mailto:support@glassnoteai.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-[var(--border)] text-sm text-[var(--text-secondary)] hover:text-white transition-colors"
            >
              Contact Support
            </a>
          )}
        </div>
        {user.plan !== "free" && (
          <p className="text-sm text-[var(--text-muted)] mt-2">
            To update your payment method, view invoices, or cancel your subscription, contact{" "}
            <a href="mailto:support@glassnoteai.com" className="text-[var(--cyan)] hover:underline">
              support@glassnoteai.com
            </a>.
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
              className={`p-5 rounded-xl border transition-colors ${isCurrent
                ? "border-[var(--cyan)] bg-[rgba(0,217,255,0.05)]"
                : "border-[var(--border)] bg-[var(--bg-card)]"
                }`}
            >
              <div className="flex items-start justify-between mb-1">
                <h3 className="text-lg font-bold text-white">{plan.display_name}</h3>
                {!isCurrent && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
                    <Clock className="w-3 h-3" />
                    Coming Soon
                  </span>
                )}
              </div>
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
                  disabled
                  className="w-full bg-[var(--bg-primary)] text-[var(--text-muted)] border border-[var(--border)] cursor-not-allowed opacity-60 font-semibold"
                >
                  <Clock className="w-4 h-4 mr-2" />
                  Coming Soon
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
