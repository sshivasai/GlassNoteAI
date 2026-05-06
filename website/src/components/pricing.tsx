/**
 * Pricing component — live data from /api/public/pricing.
 *
 * This is a Next.js Server Component (async). Pricing is fetched at
 * request time (ISR, revalidated every 5 min) so it is always in sync
 * with pricing_config.py on the backend. No hardcoding here.
 */

import { Check } from "lucide-react";
import { fetchPublicPricing, Plan } from "@/lib/api";
import { PricingCTA } from "@/components/pricing-cta";

// ── Feature labels shown on each plan card ─────────────────────────────────
// These are derived from the plan data returned by the API.

function getPlanFeatureLines(plan: Plan): string[] {
  const lines: string[] = [];

  // Sessions
  const sessions =
    plan.sessions_per_month >= 9999
      ? "Unlimited sessions"
      : plan.sessions_lifetime
        ? `${plan.sessions_per_month} lifetime sessions (no reset)`
        : `${plan.sessions_per_month} sessions per month`;
  lines.push(sessions);

  // Duration
  const duration =
    plan.session_duration_min === 0
      ? "No session time limit"
      : `${plan.session_duration_min} min per session`;
  lines.push(duration);

  // Models — show the tier label
  const modelCount = plan.allowed_models.length;
  if (modelCount >= 10) {
    lines.push("All models incl. Claude Opus & o1");
  } else if (modelCount >= 7) {
    lines.push("Claude Sonnet & GPT-4o + more");
  } else {
    lines.push("Claude Haiku & GPT-4o Mini");
  }

  // STT
  if (plan.stt_providers.includes("openai_realtime")) {
    lines.push("All STT providers");
  } else {
    lines.push("Deepgram STT");
  }

  // Feature highlights
  if (plan.features.smart_answering) {
    lines.push("Smart answering & auto-capture");
  }

  if (plan.features.priority_support) {
    lines.push("Priority support");
  } else if (plan.price_type === "free") {
    lines.push("No credit card required");
  } else {
    lines.push("Usage dashboard");
  }

  // Note: BYOK is now a user account setting, not plan-specific
  // All users can enable BYOK in Settings regardless of plan

  return lines;
}

function getPlanCTA(plan: Plan): { label: string; href: string } {
  if (plan.price_type === "free") {
    // Free plan: "Get Started Free" - no payment required
    return { label: "Start Free", href: `/signup?plan=${plan.id}` };
  }

  // Paid plans: "Subscribe" or custom label
  switch (plan.id) {
    case "base":
      return { label: "Subscribe to Base", href: "/signup?plan=base" };
    case "unlimited":
      return { label: "Go Unlimited", href: "/signup?plan=unlimited" };
    default:
      return { label: "Get Started", href: `/signup?plan=${plan.id}` };
  }
}

// ── Fallback plans (static) — shown if the API is unreachable ──────────────
const FALLBACK_PLANS: Plan[] = [
  {
    id: "free",
    display_name: "Free",
    tagline: "Try GlassNote risk-free",
    price_monthly: 0,
    price_display: "Free",
    price_type: "free",
    sessions_per_month: 5,
    sessions_lifetime: true,
    session_duration_min: 30,
    allowed_models: [],
    features: { smart_answering: false, auto_capture: false, prompt_caching: false, response_cache: true, auto_model_routing: false, http2_pooling: true, priority_support: false },
    stt_providers: ["deepgram"],
    byok_allowed: true,
    badge_color: "#888888",
    sort_order: 0,
  },
  {
    id: "base",
    display_name: "Base",
    tagline: "For regular meeting prep",
    price_monthly: 2900,
    price_display: "$29/mo",
    price_type: "subscription",
    sessions_per_month: 15,
    sessions_lifetime: false,
    session_duration_min: 60,
    allowed_models: [],
    features: { smart_answering: true, auto_capture: true, prompt_caching: true, response_cache: true, auto_model_routing: true, http2_pooling: true, priority_support: false },
    stt_providers: ["deepgram"],
    byok_allowed: true,
    badge_color: "#4f8ef7",
    sort_order: 1,
  },
  {
    id: "unlimited",
    display_name: "Unlimited",
    tagline: "All features, all models, no limits",
    price_monthly: 4900,
    price_display: "$49/mo",
    price_type: "subscription",
    sessions_per_month: 9999,
    sessions_lifetime: false,
    session_duration_min: 0,
    allowed_models: [],
    features: { smart_answering: true, auto_capture: true, prompt_caching: true, response_cache: true, auto_model_routing: true, http2_pooling: true, priority_support: true },
    stt_providers: ["deepgram", "openai_realtime"],
    byok_allowed: true,
    badge_color: "#f59e0b",
    sort_order: 2,
  },
  // Note: BYOK is now a user account setting, not a separate plan
];

// ── Component ─────────────────────────────────────────────────────────────────

export async function Pricing() {
  // Fetch live from backend; falls back to static if API is unreachable
  let plans = await fetchPublicPricing();
  if (!plans || plans.length === 0) {
    plans = FALLBACK_PLANS;
  }

  // "Base" plan is the most popular
  const popularId = "base";

  return (
    <section id="pricing" className="py-20 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-block mb-4">
            <span className="text-xs font-bold text-[var(--cyan)] tracking-widest uppercase">Pricing</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black mb-4 tracking-tight">
            Simple, transparent pricing
          </h2>
          <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto">
            Start free with BYOK (Bring Your Own Keys). Use your own API keys for unlimited access at zero cost. Open source and self-hostable.
          </p>
        </div>

        {/* BYOK Notice */}
        <div className="max-w-4xl mx-auto mb-12 p-6 rounded-xl border border-[var(--cyan)] bg-[rgba(0,217,255,0.05)] backdrop-blur-sm">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-[var(--cyan-dim)] flex items-center justify-center">
              <svg className="w-6 h-6 text-[var(--cyan)]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-white mb-2">💡 Free Forever with BYOK</h3>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                Bring Your Own API Keys (BYOK) for unlimited access at <span className="text-[var(--cyan)] font-semibold">$0 platform cost</span>.
                You pay only your AI provider (OpenAI, Anthropic, Deepgram) — typically <span className="text-[var(--lime)]">$0.50-$2 per hour</span> of meetings.
                Your data goes directly to your providers, never touching our servers.
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap justify-center gap-6 max-w-7xl mx-auto perspective-1000">
          {plans.map((plan, i) => {
            const isPopular = plan.id === popularId;
            const features = getPlanFeatureLines(plan);
            const cta = getPlanCTA(plan);

            // Display price: price_monthly is in cents
            const priceDisplay = plan.price_display;

            return (
              <div
                key={plan.id}
                className={`relative p-8 rounded-2xl border flex flex-col w-full md:w-[calc(50%-12px)] xl:w-[calc(25%-18px)] min-w-[280px] card-3d glass-panel ${isPopular
                  ? "border-[var(--cyan)] shadow-[0_0_40px_rgba(79,142,247,0.15)] md:-translate-y-4 md:scale-105 z-10"
                  : "border-[var(--border)] hover:border-[var(--border-glow)]"
                  }`}
                style={{
                  animation: `fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards`,
                  animationDelay: `${i * 0.1}s`,
                  opacity: 0,
                }}
              >
                {/* Popular badge */}
                {isPopular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs font-bold text-white bg-gradient-to-r from-[var(--cyan)] to-[var(--lime)]">
                    Most Popular
                  </div>
                )}

                <h3 className="text-2xl font-bold text-white mb-1">{plan.display_name}</h3>
                <p className="text-sm text-[var(--text-secondary)] mb-6">{plan.tagline}</p>

                {/* Price */}
                <div className="mb-6">
                  <div className="text-4xl font-black text-white">
                    {priceDisplay}
                  </div>
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8 flex-grow">
                  {features.map((feature, j) => (
                    <li key={j} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-[var(--lime)] flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-[var(--text-secondary)]">{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* CTA Button */}
                <PricingCTA planId={plan.id} label={cta.label} isPopular={isPopular} />
              </div>
            );
          })}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </section>
  );
}
