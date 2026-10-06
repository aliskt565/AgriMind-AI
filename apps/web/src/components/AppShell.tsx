"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/Button";
import { ThemeToggle } from "@/components/ThemeToggle";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", glyph: "◧" },
  { href: "/scan", label: "Scan", glyph: "🔬" },
  { href: "/farms", label: "Farms", glyph: "❖" },
  { href: "/copilot", label: "Copilot", glyph: "✦" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-[var(--color-text-muted)]">
        Loading AgriMind AI…
      </div>
    );
  }

  if (!user) {
    return null; // redirect in-flight
  }

  return (
    <div className="min-h-screen">
      <div className="flex flex-col sm:flex-row">
        <aside className="flex shrink-0 flex-row items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface-raised)]/70 px-4 py-3 backdrop-blur-sm sm:min-h-screen sm:w-56 sm:flex-col sm:items-stretch sm:justify-start sm:border-b-0 sm:border-r sm:py-6">
          <Link href="/dashboard" className="mb-0 flex items-center gap-2 px-1 sm:mb-8">
            <span aria-hidden className="text-lg text-[var(--color-ai-accent-strong)]">✦</span>
            <span className="text-lg font-semibold tracking-tight text-[var(--color-text-primary)]">AgriMind AI</span>
          </Link>
          <nav className="hidden gap-1 sm:flex sm:flex-col" aria-label="Primary">
            {NAV_ITEMS.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`group relative flex items-center gap-2.5 overflow-hidden rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-[background-color,color] duration-[var(--duration-fast)] ease-[var(--ease-standard)] ${
                    active
                      ? "bg-[var(--color-brand-soft)] text-[var(--color-brand-strong)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-[var(--color-brand-strong)] transition-transform duration-[var(--duration-normal)] ease-[var(--ease-standard)] ${
                      active ? "scale-y-100" : "scale-y-0"
                    }`}
                  />
                  <span aria-hidden className="text-sm opacity-80 transition-transform duration-[var(--duration-fast)] group-hover:translate-x-0.5">
                    {item.glyph}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="hidden sm:mt-auto sm:flex sm:flex-col sm:gap-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs text-[var(--color-text-muted)]">Theme</span>
              <ThemeToggle />
            </div>
            <Button variant="ghost" size="sm" onClick={logout} className="justify-start">
              Log out
            </Button>
          </div>
          <div className="flex items-center gap-1 sm:hidden">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={logout}>
              Log out
            </Button>
          </div>
        </aside>

        {/* Mobile bottom tab bar, per the roadmap's mobile-first requirement */}
        <nav
          aria-label="Primary mobile"
          className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-[var(--color-border)] bg-[var(--color-surface-raised)]/90 py-2 backdrop-blur-sm sm:hidden"
        >
          {NAV_ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center gap-0.5 px-4 py-1.5 text-xs font-medium transition-colors duration-[var(--duration-fast)] ${
                  active ? "text-[var(--color-brand-strong)]" : "text-[var(--color-text-muted)]"
                }`}
              >
                <span aria-hidden>{item.glyph}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="min-w-0 flex-1 px-4 pb-20 pt-6 sm:px-8 sm:pb-10">{children}</main>
      </div>
    </div>
  );
}
