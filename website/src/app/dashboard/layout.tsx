"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { LayoutDashboard, CreditCard, BarChart3, Settings, LogOut, Download } from "lucide-react";
import { Logo } from "@/components/logo";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, isAuthenticated, logout } = useAuth();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/");
    }
  }, [loading, isAuthenticated, router]);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg-deep)] flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-[var(--cyan)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  const navItems = [
    { name: "Overview",  href: "/dashboard",          icon: LayoutDashboard },
    { name: "Usage",     href: "/dashboard/usage",     icon: BarChart3 },
    { name: "Billing",   href: "/dashboard/billing",   icon: CreditCard },
    { name: "Settings",  href: "/dashboard/settings",  icon: Settings },
  ];

  const initials = ((user.first_name?.[0] || "") + (user.last_name?.[0] || "")).toUpperCase() || user.email[0].toUpperCase();

  return (
    <div className="min-h-screen bg-[var(--bg-deep)] flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[var(--border)] bg-[var(--bg-primary)] flex flex-col">
        <div className="p-6">
          <Link href="/" className="flex items-center gap-2 text-xl font-bold">
            <Logo className="w-8 h-8 rounded-lg" />
            <span className="text-white">GlassNote</span>
          </Link>
        </div>

        <nav className="flex-1 px-4 space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive
                    ? "bg-[rgba(0,217,255,0.1)] text-[var(--cyan)]"
                    : "text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium text-sm">{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-[var(--border)]">
          <div className="flex items-center gap-3 px-3 py-2 mb-2">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--cyan-dim)] to-[var(--lime-dim)] flex items-center justify-center border border-[var(--border)]">
              <span className="text-xs font-bold text-[var(--cyan)]">{initials}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {user.first_name ? `${user.first_name} ${user.last_name}` : user.email}
              </p>
              <p className="text-xs text-[var(--text-muted)] capitalize">{user.plan} Plan</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-red-500/10 hover:text-red-400 transition-colors"
          >
            <LogOut className="w-5 h-5" />
            <span className="font-medium text-sm">Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-5xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
