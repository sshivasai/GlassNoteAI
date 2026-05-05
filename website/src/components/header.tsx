"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";

interface HeaderProps {
  showTestimonials?: boolean;
}

export function Header({ showTestimonials = true }: HeaderProps) {
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
          {showTestimonials && (
            <li>
              <a href="#testimonials" className="text-[var(--text-secondary)] hover:text-white transition">
                Reviews
              </a>
            </li>
          )}
          <li>
            <a
              href="https://github.com/sshivasai/GlassNoteAI"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--text-secondary)] hover:text-white transition flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              GitHub
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
