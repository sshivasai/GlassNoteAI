"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";

export function Header() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { isAuthenticated, user, openAuth, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 40);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? "bg-[var(--bg-deep)]/80 backdrop-blur-md border-b border-[var(--border)]" : "bg-transparent"
        }`}
    >
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 text-xl font-bold tracking-tight">
          <Logo className="w-8 h-8 rounded-md" />
          <span className="text-white">GlassNote</span>
        </Link>

        {/* Nav Links */}
        <ul className="hidden md:flex items-center gap-8 text-sm font-medium">
          <li>
            <a href="#features" className="text-[var(--text-secondary)] hover:text-white transition">
              Features
            </a>
          </li>
          <li>
            <a href="#how-it-works" className="text-[var(--text-secondary)] hover:text-white transition">
              How It Works
            </a>
          </li>
          <li>
            <a href="#pricing" className="text-[var(--text-secondary)] hover:text-white transition">
              Pricing
            </a>
          </li>
          <li>
            <a href="#testimonials" className="text-[var(--text-secondary)] hover:text-white transition">
              Reviews
            </a>
          </li>
        </ul>

        {/* CTA Buttons */}
        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <div className="relative">
              <Button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="bg-white text-black hover:bg-gray-100 font-medium px-5 flex items-center gap-2"
              >
                <User className="w-4 h-4" />
                <span className="hidden sm:inline">{user?.first_name || "Account"}</span>
              </Button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg shadow-lg overflow-hidden z-50">
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      router.push("/dashboard");
                    }}
                    className="w-full px-4 py-2.5 text-left text-sm text-white hover:bg-white/5 transition flex items-center gap-2"
                  >
                    <User className="w-4 h-4" />
                    Dashboard
                  </button>
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      logout();
                      router.push("/");
                    }}
                    className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-red-500/10 transition flex items-center gap-2 border-t border-[var(--border)]"
                  >
                    <LogOut className="w-4 h-4" />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => openAuth("login")}
                className="hidden sm:inline-flex text-[var(--text-secondary)] hover:text-white hover:bg-white/5"
              >
                Sign In
              </Button>
              <Button
                onClick={() => openAuth("signup")}
                className="bg-white text-black hover:bg-gray-100 font-medium px-5"
              >
                Get Started
              </Button>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
