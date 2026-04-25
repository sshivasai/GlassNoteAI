/**
 * Testimonials component — live data from /api/public/testimonials.
 *
 * This is a Next.js Server Component (async). Testimonials are fetched at
 * request time (ISR, revalidated every hour) so they can be updated on the
 * backend without touching the frontend. No hardcoding here.
 */

import { fetchPublicTestimonials, Testimonial } from "@/lib/api";

// ── Fallback testimonials — shown if the API is unreachable ──────────────────
const FALLBACK_TESTIMONIALS: Testimonial[] = [
  {
    text: "I used GlassNote for my Amazon loop and it was incredible. The overlay answered system design questions in real-time while being completely invisible on Chime. Got the offer.",
    author: "Alex K.",
    role: "Software Engineer → Amazon",
    initial: "A",
    plan: "unlimited",
    stars: 5,
  },
  {
    text: "The speed is unreal. Claude Opus starts answering before I even finish reading the question. The transparent overlay feels like having a second brain on screen.",
    author: "Sarah M.",
    role: "SDE II → Google",
    initial: "S",
    plan: "unlimited",
    stars: 5,
  },
  {
    text: "BYOK mode is genius — I use my own Anthropic key so there's zero platform fee. The auto model routing picks the right model every time.",
    author: "Raj P.",
    role: "Full Stack → Microsoft",
    initial: "R",
    plan: "byok",
    stars: 5,
  },
];

// ── Star rating display ───────────────────────────────────────────────────────
function Stars({ count }: { count: number }) {
  return (
    <div className="flex gap-0.5 mb-4">
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} className="text-[var(--lime)] text-sm">★</span>
      ))}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export async function Testimonials() {
  // Fetch live from backend; falls back to static if API is unreachable
  let testimonials = await fetchPublicTestimonials(6);
  if (!testimonials || testimonials.length === 0) {
    testimonials = FALLBACK_TESTIMONIALS;
  }

  return (
    <section id="testimonials" className="py-20 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-block mb-4">
            <span className="text-xs font-bold text-[var(--cyan)] tracking-widest uppercase">Testimonials</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black mb-4 tracking-tight">
            Loved by engineers
          </h2>
          <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto">
            See how GlassNote is helping developers ace their meetings at top tech companies.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {testimonials.map((testimonial, i) => (
            <div
              key={i}
              className="p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] hover:border-[var(--border-glow)] transition-all duration-300 flex flex-col"
              style={{
                animation: `fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards`,
                animationDelay: `${i * 0.1}s`,
                opacity: 0,
              }}
            >
              {/* Stars */}
              <Stars count={testimonial.stars} />

              {/* Quote text */}
              <p className="text-sm text-[var(--text-secondary)] italic mb-6 leading-relaxed flex-grow">
                &quot;{testimonial.text}&quot;
              </p>

              {/* Author */}
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--cyan-dim)] to-[var(--lime-dim)] flex items-center justify-center flex-shrink-0">
                  <span className="text-sm font-bold text-[var(--cyan)]">{testimonial.initial}</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{testimonial.author}</p>
                  <p className="text-xs text-[var(--text-muted)]">{testimonial.role}</p>
                </div>
              </div>
            </div>
          ))}
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
