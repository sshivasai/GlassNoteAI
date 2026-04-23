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
    if (plan.byok_allowed) {
      lines.push("Bring your own Anthropic/OpenAI keys");
    } else {
      lines.push("Smart answering & auto-capture");
    }
  }

  if (plan.features.priority_support) {
    lines.push("Priority support");
  } else if (plan.price_type === "free") {
    lines.push("No credit card required");
  } else {
    lines.push("Usage dashboard");
  }

  if (plan.byok_allowed) {
    lines.push("Zero platform API cost");
  }

  return lines;
}

function getPlanCTA(plan: Plan): { label: string; href: string } {
  switch (plan.id) {
    case "free":
      return { label: "Start Free", href: "/signup" };
    case "base":
      return { label: "Get Base", href: "/signup?plan=base" };
    case "unlimited":
      return { label: "Go Unlimited", href: "/signup?plan=unlimited" };
    case "byok":
      return { label: "Get Lifetime Access", href: "/signup?plan=byok" };
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
    byok_allowed: false,
    badge_color: "#888888",
    sort_order: 0,
  },
  {
    id: "base",
    display_name: "Base",
    tagline: "For regular interview prep",
    price_monthly: 2900,
    price_display: "$29/mo",
    price_type: "subscription",
    sessions_per_month: 15,
    sessions_lifetime: false,
    session_duration_min: 60,
    allowed_models: [],
    features: { smart_answering: true, auto_capture: true, prompt_caching: true, response_cache: true, auto_model_routing: true, http2_pooling: true, priority_support: false },
    stt_providers: ["deepgram"],
    byok_allowed: false,
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
    byok_allowed: false,
    badge_color: "#f59e0b",
    sort_order: 2,
  },
  {
    id: "byok",
    display_name: "BYOK",
    tagline: "Use your own API keys forever",
    price_monthly: 9900,
    price_display: "$99 forever",
    price_type: "one_time",
    sessions_per_month: 9999,
    sessions_lifetime: false,
    session_duration_min: 0,
    allowed_models: [],
    features: { smart_answering: true, auto_capture: true, prompt_caching: true, response_cache: true, auto_model_routing: true, http2_pooling: true, priority_support: true },
    stt_providers: ["deepgram", "openai_realtime"],
    byok_allowed: true,
    badge_color: "#10b981",
    sort_order: 3,
  },
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
            Start free, no credit card needed. Upgrade when you&apos;re ready — or bring your own API keys for a one-time lifetime purchase.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 max-w-6xl mx-auto perspective-1000">
          {plans.map((plan, i) => {
            const isPopular = plan.id === popularId;
            const features  = getPlanFeatureLines(plan);
            const cta       = getPlanCTA(plan);

            // Display price: price_monthly is in cents
            const priceDisplay = plan.price_display;

            return (
              <div
                key={plan.id}
                className={`relative p-8 rounded-2xl border flex flex-col h-full card-3d glass-panel ${
                  isPopular
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
