"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

// This page is replaced by the modal auth flow.
// If someone navigates to /signup directly, open the signup modal on the homepage.
export default function SignupPage() {
  const { openAuth } = useAuth();

  useEffect(() => {
    openAuth("signup");
  }, [openAuth]);

  return (
    <div className="min-h-screen bg-[var(--bg-deep)] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
