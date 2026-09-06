"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  CloudLightning,
  CloudSun,
  Database,
  Layers,
  MessageSquareCode,
  Radio,
  Server,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "COMMAND CENTER", href: "/command-center", icon: CloudLightning },
  { label: "LIVE WEATHER", href: "/live-weather", icon: CloudSun },
  { label: "INCIDENTS", href: "/incidents", icon: Layers },
  { label: "LIVE FEED", href: "/live-feed", icon: Radio },
  { label: "ANALYTICS", href: "/analytics", icon: BarChart3 },
  { label: "EARLY WARNING", href: "/early-warning", icon: AlertTriangle },
  { label: "VERIFICATION", href: "/verification", icon: ShieldCheck },
  { label: "WEATHERGPT", href: "/weathergpt", icon: MessageSquareCode },
  { label: "SYSTEM HEALTH", href: "/system-health", icon: Server },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState<boolean>(false);

  return (
    <aside
      className={`relative flex flex-col bg-panel border-r border-borderSubtle transition-all duration-200 ease-in-out z-30 ${
        collapsed ? "w-16" : "w-60"
      }`}
    >
      {/* Platform Branding Header */}
      <div className="h-14 px-4 flex items-center justify-between border-b border-borderSubtle bg-panelRaised/40">
        <Link href="/command-center" className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded bg-accent/20 border border-accent/40 flex items-center justify-center flex-shrink-0">
            <CloudLightning className="w-4 h-4 text-accent" />
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="font-display text-sm font-bold tracking-wider text-textPrimary truncate leading-tight">
                NAT-WEATHER OPS
              </span>
              <span className="text-[10px] font-mono text-textSecondary tracking-widest uppercase">
                SIH PLATFORM • 2026
              </span>
            </div>
          )}
        </Link>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          // Match direct or alias route
          const isActive =
            pathname === item.href ||
            (item.href === "/command-center" && (pathname === "/" || pathname === "/dashboard")) ||
            (item.href === "/verification" && pathname === "/admin");

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`flex items-center gap-3 px-3 py-2.5 rounded transition-all group ${
                isActive
                  ? "bg-accent/15 text-accent border border-accent/40 font-semibold shadow-sm"
                  : "text-textSecondary hover:text-textPrimary hover:bg-white/5 border border-transparent"
              }`}
            >
              <Icon
                className={`w-4 h-4 flex-shrink-0 transition-colors ${
                  isActive ? "text-accent" : "text-textDisabled group-hover:text-textSecondary"
                }`}
              />
              {!collapsed && (
                <span className="truncate flex-1 font-display text-[13px] font-semibold tracking-wider uppercase">
                  {item.label}
                </span>
              )}
              {!collapsed && item.badge && (
                <span className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom Status & Collapse Toggle */}
      <div className="p-3 border-t border-borderSubtle bg-panelRaised/30 space-y-2">
        {!collapsed && (
          <div className="bg-background/80 border border-borderSubtle rounded p-2 text-[10px] font-mono space-y-1">
            <div className="flex items-center justify-between text-textSecondary">
              <span>POSTGIS ENGINE:</span>
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                SYNCED
              </span>
            </div>
            <div className="flex items-center justify-between text-textSecondary">
              <span>ACTIVE FEEDS:</span>
              <span className="text-live font-semibold">4 / 4 UP</span>
            </div>
          </div>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full py-1.5 px-2 rounded border border-borderSubtle hover:bg-white/5 text-textSecondary hover:text-textPrimary flex items-center justify-center transition-colors text-xs"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <div className="flex items-center gap-1 text-[10px] font-mono text-textDisabled">
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>COLLAPSE CONSOLE</span>
            </div>
          )}
        </button>
      </div>
    </aside>
  );
}
