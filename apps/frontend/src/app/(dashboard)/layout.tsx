"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutGrid,
  Bell,
  Layers,
  ScanEye,
  KeyRound,
  FileCheck2,
  LogOut,
  Menu,
  X,
  ArrowUpRight,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
const ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutGrid },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/events", label: "Audit log", icon: Layers },
  { href: "/ai-agents", label: "AI agents", icon: ScanEye },
  { href: "/api-keys", label: "API keys", icon: KeyRound },
  { href: "/compliance", label: "Compliance", icon: FileCheck2 },
];
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    if (!isLoading && !user) router.push("/login");
  }, [user, isLoading, router]);
  if (isLoading)
    return (
      <div className="loading-screen" role="status">
        <span className="loading-spinner" />
        Opening your workspace…
      </div>
    );
  if (!user) return null;
  const title =
    ITEMS.find((i) => pathname.startsWith(i.href))?.label ?? "Investigation";
  return (
    <div className="workspace">
      <aside
        id="workspace-navigation"
        className={cn("workspace-sidebar", menuOpen && "is-open")}
      >
        <div className="sidebar-brand">
          <Brand />
          <button
            className="mobile-close"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="workspace-label">
          WORKSPACE<span>01</span>
        </div>
        <nav aria-label="Workspace navigation">
          {ITEMS.map((i) => (
            <Link
              key={i.href}
              href={i.href}
              onClick={() => setMenuOpen(false)}
              aria-current={pathname.startsWith(i.href) ? "page" : undefined}
              className={cn(
                "sidebar-link",
                pathname.startsWith(i.href) && "active",
              )}
            >
              <i.icon size={18} strokeWidth={1.6} />
              {i.label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <Link href="/developers" className="sidebar-guide">
            <span>
              Build with Sentinel<small>Explore the developer guide</small>
            </span>
            <ArrowUpRight size={17} />
          </Link>
          <div className="user-profile">
            <span className="avatar">
              {(user.full_name || user.email).slice(0, 1).toUpperCase()}
            </span>
            <div>
              <strong>{user.full_name || user.email.split("@")[0]}</strong>
              <span>{user.role.toLowerCase()} · Workspace access</span>
            </div>
            <button onClick={logout} aria-label="Sign out" title="Sign out">
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {menuOpen && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <div className="workspace-body">
        <header className="workspace-toolbar">
          <div>
            <button
              className="mobile-menu"
              aria-label="Open navigation"
              aria-expanded={menuOpen}
              aria-controls="workspace-navigation"
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              Workspace <span>/</span> <strong>{title}</strong>
            </span>
          </div>
          <div className="toolbar-links">
            <Link href="/status">
              <span className="status-dot" /> System status
            </Link>
            <span className="environment-label">Development</span>
          </div>
        </header>
        <main className="workspace-content">{children}</main>
        <footer className="workspace-footer">
          <span>Sentinel 2 · Watchful by design</span>
          <Link href="/developers">Documentation ↗</Link>
        </footer>
      </div>
    </div>
  );
}
