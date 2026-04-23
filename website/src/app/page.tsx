import { Header } from "@/components/header";
import { Hero } from "@/components/hero";
import { Features } from "@/components/features";
import { HowItWorks } from "@/components/how-it-works";
import { Pricing } from "@/components/pricing";
import { Testimonials } from "@/components/testimonials";
import { CTA } from "@/components/cta";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-[var(--bg-deep)] to-[var(--bg-primary)]">
      <Header />
      <Hero />
      <div className="w-full h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-40 shadow-[0_0_15px_var(--cyan)]" />
      <Features />
      <div id="how-it-works" className="w-full h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-40 shadow-[0_0_15px_var(--cyan)]" />
      <HowItWorks />
      <div className="w-full h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-40 shadow-[0_0_15px_var(--cyan)]" />
      <div id="pricing">
        <Pricing />
      </div>
      <div className="w-full h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-40 shadow-[0_0_15px_var(--cyan)]" />
      <div id="testimonials">
        <Testimonials />
      </div>
      <div className="w-full h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-40 shadow-[0_0_15px_var(--cyan)]" />
      <CTA />
      <Footer />
    </main>
  );
}
