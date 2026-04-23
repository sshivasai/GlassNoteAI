import React from "react";

const DeepgramIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
  </svg>
);

const ScreenIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="2" fill="none" />
    <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

const AILogos = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    {/* Simplified Anthropic Star & OpenAI Flower concept */}
    <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9588 3.7411 6.0051 6.0051 0 0 0 1.7243 6.6789 5.9847 5.9847 0 0 0 .5157 4.9108 6.0462 6.0462 0 0 0 6.5098 2.9 6.0651 6.0651 0 0 0 10.2764-2.1709 5.9847 5.9847 0 0 0 3.9588-3.7411 6.0051 6.0051 0 0 0-1.7243-6.6789ZM10.92 21.181a4.9408 4.9408 0 0 1-2.514-1.257l2.514-1.451v2.708ZM4.08 14.12l2.514 1.451-2.514-1.451ZM6.594 5.61l2.514 1.451L6.594 5.61ZM17.406 5.61l-2.514 1.451 2.514-1.451ZM19.92 14.12l-2.514 1.451 2.514-1.451ZM13.08 21.181v-2.708l2.514 1.451a4.9408 4.9408 0 0 1-2.514 1.257ZM12 15.115l-2.514-1.451v-2.903L12 9.31l2.514 1.451v2.903L12 15.115Z" />
  </svg>
);

const GhostIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M12 2C8.686 2 6 4.686 6 8v14l3-3 3 3 3-3 3 3V8c0-3.314-2.686-6-6-6z" opacity="0.8"/>
  </svg>
);

const LightningIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
  </svg>
);

const KeyIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M12.65 10A5.99 5.99 0 0 0 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6a5.99 5.99 0 0 0 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z" />
  </svg>
);

const features = [
  {
    icon: DeepgramIcon,
    title: "Real-Time Transcription",
    description: "Listens to your interview conversation via system audio or microphone. Supports Deepgram and OpenAI Realtime STT with ultra-low latency.",
  },
  {
    icon: ScreenIcon,
    title: "Smart Screen Capture",
    description: "Automatically detects and captures coding problems, system design diagrams, and questions from your screen.",
  },
  {
    icon: AILogos,
    title: "Claude & GPT Powered",
    description: "Choose between Claude Opus, Sonnet, Haiku, GPT-4o, or GPT-4. Auto-routing selects the optimal model.",
  },
  {
    icon: GhostIcon,
    title: "Invisible Overlay",
    description: "The transparent glass overlay is completely invisible to screen sharing tools. Works on Zoom, Teams, Meet, and more.",
  },
  {
    icon: LightningIcon,
    title: "Sub-300ms Response",
    description: "Speculative connection pre-warming, HTTP/2 connection pools, and zero-copy streaming ensure fast responses.",
  },
  {
    icon: KeyIcon,
    title: "Bring Your Own Keys",
    description: "Use GlassNote Cloud for managed access, or bring your own API keys. Your data never touches our servers in BYOK mode.",
  },
];

export function Features() {
  return (
    <section id="features" className="py-20 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-block mb-4">
            <span className="text-xs font-bold text-[var(--cyan)] tracking-widest uppercase">Features</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black mb-4 tracking-tight">
            Everything you need to<br />ace your interview
          </h2>
          <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto">
            GlassNote combines real-time audio transcription, screen analysis, and AI reasoning into a seamless invisible overlay.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 perspective-1000">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <div className="animate-float" style={{ animationDelay: `${i * 0.5}s` }} key={i}>
                <div
                  className="group h-full p-6 rounded-xl border border-[var(--border)] glass-panel card-3d"
                  style={{
                    animation: `fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards`,
                    animationDelay: `${i * 0.1}s`,
                    opacity: 0,
                  }}
                >
                  <div className="w-12 h-12 rounded-xl bg-[var(--cyan-dim)] flex items-center justify-center mb-4 group-hover:bg-[rgba(0,217,255,0.2)] transition-colors">
                    <Icon className="w-7 h-7 text-[var(--cyan)]" />
                  </div>
                  <h3 className="text-lg font-bold mb-2 text-white">{feature.title}</h3>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{feature.description}</p>
                </div>
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
