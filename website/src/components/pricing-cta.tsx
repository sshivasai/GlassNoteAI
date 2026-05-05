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

  // Mark base and unlimited as coming soon
  const isComingSoon = planId === "base" || planId === "unlimited";

  const handleClick = () => {
    if (isComingSoon) {
      return; // Do nothing for coming soon plans
    }

    // Free plan — just get started (no billing needed)
    if (planId === "free") {
      isAuthenticated ? router.push("/dashboard") : openAuth("signup");
      return;
    }
    // Paid plans — need billing
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
      disabled={isComingSoon}
      className={`w-full h-11 font-semibold ${
        isComingSoon
          ? "bg-[var(--bg-card)] border border-[var(--border)] text-[var(--text-muted)] cursor-not-allowed opacity-60"
          : isPopular
          ? "bg-[var(--cyan)] text-black hover:bg-[#00f0ff]"
          : "border border-[var(--border)] text-white hover:bg-[var(--cyan-dim)]"
      }`}
    >
      {isComingSoon ? "Coming Soon" : label}
    </Button>
  );
}
