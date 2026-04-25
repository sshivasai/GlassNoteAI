"use client";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";

export function CTA() {
  const { openAuth } = useAuth();

  return (
    <section className="relative py-20 px-4 overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-[var(--cyan)] rounded-full blur-3xl opacity-[0.06]" />
      </div>

      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-4xl md:text-5xl font-black mb-6 tracking-tight">
          Ready to ace your
          <br />
          <span className="bg-gradient-to-r from-[var(--cyan)] to-[var(--lime)] bg-clip-text text-transparent">
            next meeting?
          </span>
        </h2>

        <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto mb-8">
          Download GlassNote now — free forever with your own API keys.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <Button
            size="lg"
            onClick={() => openAuth("signup")}
            className="bg-[var(--cyan)] text-white hover:opacity-90 font-semibold px-8 h-12 flex items-center gap-2 shadow-[0_0_20px_var(--cyan-dim)] transition-transform duration-300 hover:scale-105"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.951-1.801" />
            </svg>
            Download for Windows
          </Button>
          <Button
            size="lg"
            onClick={() => { document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' }); }}
            className="border-2 border-[var(--cyan)] text-[var(--cyan)] bg-transparent hover:bg-[var(--cyan-dim)] font-semibold px-8 h-12 transition-transform duration-300 hover:scale-105"
          >
            View Plans →
          </Button>
        </div>
      </div>
    </section>
  );
}
