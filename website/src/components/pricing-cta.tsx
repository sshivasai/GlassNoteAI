"use client";

import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

interface PricingCTAProps {
  planId: string;
  label: string;
  isPopular: boolean;
}

export function PricingCTA({ planId, label, isPopular }: PricingCTAProps) {
  const { isAuthenticated, openAuth } = useAuth();
  const router = useRouter();

  const handleClick = () => {
    // FIX: Handle both free and BYOK as free plans (no payment needed)
    if (planId === "free" || planId === "byok") {
      // Free plans — just get started (no billing)
      isAuthenticated ? router.push("/dashboard") : openAuth("signup");
      return;
    }
    // Paid plans (base, unlimited) — need billing
    if (isAuthenticated) {
      // Already logged in — go to billing to upgrade
      router.push("/dashboard/billing");
    } else {
      // Not logged in — open signup first
      openAuth("signup");
    }
  };

  return (
    <Button
      onClick={handleClick}
      className={`w-full h-11 font-semibold ${
        isPopular
          ? "bg-[var(--cyan)] text-black hover:bg-[#00f0ff]"
          : "border border-[var(--border)] text-white hover:bg-[var(--cyan-dim)]"
      }`}
    >
      {label}
    </Button>
  );
}
