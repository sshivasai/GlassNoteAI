export function HowItWorks() {
  const steps = [
    {
      number: 1,
      title: "Download & Install",
      description: "One-click Windows installer. No dependencies, no admin rights needed. Under 50MB.",
    },
    {
      number: 2,
      title: "Configure Settings",
      description: "Add your API keys or sign in to GlassNote Cloud. Select your preferred AI models and customize your preferences.",
    },
    {
      number: 3,
      title: "Join Your Meeting",
      description: "GlassNote listens via system audio and monitors your screen. Press a hotkey whenever you need assistance.",
    },
    {
      number: 4,
      title: "Get Instant Help",
      description: "Real-time AI responses appear in a transparent overlay visible only to you. Completely invisible during screen sharing.",
    },
  ];

  return (
    <section id="how-it-works" className="py-20 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <div className="inline-block mb-4">
            <span className="text-xs font-bold text-[var(--cyan)] tracking-widest uppercase">How It Works</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-black mb-4 tracking-tight">
            Set up in 60 seconds
          </h2>
          <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto">
            No complex configuration needed. Just download, add your API key or sign in, and start your meeting session.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((step, i) => (
            <div
              key={i}
              className="relative p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] hover:border-[var(--border-glow)] transition-all duration-300"
              style={{
                animation: `fadeIn 0.7s cubic-bezier(0.4, 0, 0.2, 1) forwards`,
                animationDelay: `${i * 0.1}s`,
                opacity: 0,
              }}
            >
              {/* Step number badge */}
              <div className="w-10 h-10 rounded-lg bg-[var(--cyan-dim)] flex items-center justify-center mb-4 border border-[rgba(0,217,255,0.15)]">
                <span className="text-sm font-bold text-[var(--cyan)]">{step.number}</span>
              </div>

              <h3 className="text-lg font-bold mb-2 text-white">{step.title}</h3>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{step.description}</p>

              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden lg:block absolute top-1/2 -right-3 w-6 h-px bg-gradient-to-r from-[var(--cyan)] to-transparent" />
              )}
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
