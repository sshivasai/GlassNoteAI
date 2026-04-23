"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

// This page is replaced by the modal auth flow.
// If someone navigates to /login directly, open the modal on the homepage.
export default function LoginPage() {
  const { openAuth } = useAuth();

  useEffect(() => {
    openAuth("login");
  }, [openAuth]);

  return (
    <div className="min-h-screen bg-[var(--bg-deep)] flex items-center justify-center">
      <div className="w-8 h-8 border-4 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
