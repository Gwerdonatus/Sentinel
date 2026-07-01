"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: "⬛", exact: true },
  { href: "/alerts", label: "Alerts", icon: "🔔", exact: false },
  { href: "/events", label: "Audit Log", icon: "📋", exact: false },
  { href: "/ai-agents", label: "AI Agents", icon: "🤖", exact: false },
  { href: "/api-keys", label: "API Keys", icon: "🔑", exact: false },
  { href: "/compliance", label: "Compliance", icon: "📄", exact: false },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-sentinel-500 border-t-transparent" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r border-gray-800 bg-gray-900/50">
        {/* Brand */}
        <div className="flex h-14 items-center gap-2.5 border-b border-gray-800 px-4">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-sentinel-600 text-xs">
            🛡️
          </div>
          <span className="font-semibold text-white">Sentinel</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5 p-2">
          {NAV_ITEMS.map((item) => {
            const isActive = item.exact
              ? pathname === item.href
              : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-sentinel-900/60 text-sentinel-300"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                )}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="border-t border-gray-800 p-3">
          <div className="mb-2 rounded-md bg-gray-800/60 px-3 py-2">
            <p className="truncate text-xs font-medium text-white">{user.full_name || user.email}</p>
            <p className="text-xs text-gray-500">{user.role}</p>
          </div>
          <button
            onClick={logout}
            className="w-full rounded-md px-3 py-1.5 text-left text-xs text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-300"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
