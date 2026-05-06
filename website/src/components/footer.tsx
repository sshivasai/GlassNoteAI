import { Logo } from "@/components/logo";
import { DOWNLOAD_URL } from "@/lib/config";

const footerLinks = {
  product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Download", href: DOWNLOAD_URL, external: true },
  ],
  resources: [
    { label: "GitHub", href: "https://github.com/sshivasai/GlassNoteAI", external: true },
    { label: "Documentation", href: "#" },
    { label: "Support", href: "mailto:support@glassnote.ai" },
    { label: "Status", href: "#" },
  ],
  legal: [
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
    { label: "License", href: "https://github.com/sshivasai/GlassNoteAI/blob/main/LICENSE", external: true },
  ],
};

export function Footer() {
  return (
    <footer className="border-t border-[var(--border)] py-16 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Main footer content */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          {/* Brand */}
          <div className="md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <Logo className="w-8 h-8 rounded-lg" />
              <span className="text-lg font-bold text-white">GlassNote</span>
            </div>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed mb-3">
              Speak confidently in every meeting with real-time AI assistance. Open source and privacy-focused.
            </p>
            <a href="https://github.com/sshivasai/GlassNoteAI" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-xs text-[var(--cyan)] hover:text-[var(--lime)] transition-colors">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              View on GitHub
            </a>
          </div>

          {/* Product Links */}
          <div>
            <h4 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-4">Product</h4>
            <ul className="space-y-3">
              {footerLinks.product.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-[var(--text-muted)] hover:text-white transition"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources Links */}
          <div>
            <h4 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-4">Resources</h4>
            <ul className="space-y-3">
              {footerLinks.resources.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-[var(--text-muted)] hover:text-white transition"
                    {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Legal Links */}
          <div>
            <h4 className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-widest mb-4">Legal</h4>
            <ul className="space-y-3">
              {footerLinks.legal.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-[var(--text-muted)] hover:text-white transition"
                    {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom section */}
        <div className="border-t border-[var(--border)] pt-8">
          <p className="text-sm text-[var(--text-muted)] text-center">
            © 2026 GlassNote. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
