"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  Bell,
  Clock,
  Globe,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";

const SECTION_TITLES: Record<string, { title: string; subtitle: string }> = {
  "/command-center": { title: "NATIONAL SITUATION OVERVIEW", subtitle: "Strategic Weather & Disaster Command" },
  "/dashboard": { title: "NATIONAL SITUATION OVERVIEW", subtitle: "Strategic Weather & Disaster Command" },
  "/live-weather": { title: "GEOSPATIAL WEATHER INTELLIGENCE", subtitle: "Multi-Provider Observation & Forecast Workspace" },
  "/incidents": { title: "INCIDENT RESPONSE MANAGEMENT", subtitle: "Active Weather Cluster Operations & Tracking" },
  "/live-feed": { title: "REAL-TIME INGESTION FEED", subtitle: "Continuous Multi-Source Report Stream & Triage" },
  "/analytics": { title: "BIG DATA ANALYTICS & QUALITY", subtitle: "Data Engineering Metrics & Pipeline Reliability" },
  "/early-warning": { title: "EARLY WARNING & ESCALATION", subtitle: "Platform-Assisted Emerging Severe Weather Detection" },
  "/verification": { title: "HUMAN-IN-THE-LOOP VERIFICATION", subtitle: "Triage & Moderation Queue for Citizen Reports" },
  "/admin": { title: "HUMAN-IN-THE-LOOP VERIFICATION", subtitle: "Triage & Moderation Queue for Citizen Reports" },
  "/weathergpt": { title: "WEATHERGPT DECISION SUPPORT", subtitle: "Conversational Meteorological & Platform Intelligence" },
  "/system-health": { title: "SYSTEM ARCHITECTURE & HEALTH", subtitle: "Infrastructure Diagnostics & Pipeline Topology" },
};

export function TopBar({
  onRefresh,
  refreshing = false,
  isDemoMode = false,
}: {
  onRefresh?: () => void;
  refreshing?: boolean;
  isDemoMode?: boolean;
}) {
  const pathname = usePathname();
  const [currentTime, setCurrentTime] = useState({
    utc: "",
    ist: "",
  });
  const [alerts, setAlerts] = useState<any[]>([]);
  const [showAlertsDrawer, setShowAlertsDrawer] = useState<boolean>(false);

  // Synchronized UTC + IST Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime({
        utc: now.toUTCString().replace("GMT", "UTC").slice(17, 25) + " UTC",
        ist: now.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }) + " IST",
      });
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch active alerts count with real-time 5s polling
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiUrl}/api/alerts`);
        if (res.ok) {
          const data = await res.json();
          setAlerts(data || []);
        }
      } catch (e) {
        // Fallback silently
      }
    };
    fetchAlerts();
    const alertInterval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(alertInterval);
  }, []);

  const meta = SECTION_TITLES[pathname] || {
    title: "NATIONAL WEATHER PLATFORM",
    subtitle: "Real-Time Big Data Analytics",
  };

  const highSeverityCount = alerts.filter(
    (a) => a.severity === "critical" || a.severity === "high"
  ).length;

  return (
    <header className="sticky top-0 z-20 bg-panel/95 backdrop-blur-md border-b border-borderSubtle">
      {/* Demo Mode Notice Banner if demo dataset active */}
      {isDemoMode && (
        <div className="bg-amber-500/15 border-b border-amber-500/30 px-4 py-1 flex items-center justify-between text-[11px] font-mono text-amber-300">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-bold uppercase tracking-wider">
              DEMO MODE — Deterministic sample dataset active
            </span>
          </div>
          <span className="text-[10px] text-amber-400/80">
            Simulated Indian Weather Events (Monsoon Scenario)
          </span>
        </div>
      )}

      {/* Top Main Navigation Bar */}
      <div className="h-14 px-4 sm:px-6 flex items-center justify-between gap-4">
        {/* Breadcrumb Context */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex flex-col min-w-0">
            <h1 className="font-display text-sm sm:text-base font-bold tracking-wider text-textPrimary truncate uppercase">
              {meta.title}
            </h1>
            <span className="text-[11px] text-textSecondary font-sans font-medium hidden sm:block truncate">
              {meta.subtitle}
            </span>
          </div>
        </div>

        {/* Right Operations Telemetry */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Synchronized Clocks */}
          <div className="hidden lg:flex items-center gap-3 bg-panelRaised px-3 py-1.5 rounded border border-borderSubtle font-mono text-[11px] tabular-nums">
            <div className="flex items-center gap-1.5 text-textPrimary">
              <Clock className="w-3.5 h-3.5 text-accent" />
              <span>{currentTime.ist || "00:00:00 IST"}</span>
            </div>
            <span className="text-borderStrong">|</span>
            <div className="text-textSecondary">
              <span>{currentTime.utc || "00:00:00 UTC"}</span>
            </div>
          </div>

          {/* Active Alerts Pill Button */}
          <button
            onClick={() => setShowAlertsDrawer(!showAlertsDrawer)}
            className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded border font-display tracking-wider text-xs font-bold transition-colors ${
              highSeverityCount > 0
                ? "bg-red-500/15 border-red-500/40 text-red-400 hover:bg-red-500/25"
                : "bg-panelRaised border-borderSubtle text-textSecondary hover:text-textPrimary"
            }`}
            title="View Active Platform Alerts"
          >
            <AlertTriangle className={`w-3.5 h-3.5 ${highSeverityCount > 0 ? "animate-pulse text-red-400" : "text-textDisabled"}`} />
            <span>ALERTS: {alerts.length}</span>
            {highSeverityCount > 0 && (
              <span className="w-2 h-2 rounded-full bg-red-500 animate-ping absolute -top-0.5 -right-0.5" />
            )}
          </button>

          {/* Refresh Action */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="p-2 rounded border border-borderSubtle bg-panelRaised hover:bg-white/5 text-textSecondary hover:text-textPrimary transition-colors"
              title="Refresh Current Telemetry"
              aria-label="Refresh Data"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-accent ${refreshing ? "animate-spin" : ""}`} />
            </button>
          )}

          {/* Stream Connection Live Indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-panelRaised border border-borderSubtle text-[11px] font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400/50" />
            <span className="text-textPrimary hidden sm:inline">OPS LIVE</span>
          </div>
        </div>
      </div>

      {/* Slide-down alert drawer if toggled */}
      {showAlertsDrawer && (
        <div className="border-t border-borderStrong bg-panelRaised/95 backdrop-blur-md px-6 py-3 text-xs max-h-48 overflow-y-auto space-y-2 animate-fadeIn">
          <div className="flex items-center justify-between text-[11px] font-mono text-textSecondary border-b border-borderSubtle pb-1.5">
            <span className="font-bold uppercase text-textPrimary">
              Active Platform Early Warnings & Escalations ({alerts.length})
            </span>
            <button
              onClick={() => setShowAlertsDrawer(false)}
              className="text-textDisabled hover:text-textPrimary"
            >
              [Dismiss]
            </button>
          </div>
          {alerts.length === 0 ? (
            <div className="text-textDisabled py-2 font-mono text-[11px]">
              No active critical alerts detected across India.
            </div>
          ) : (
            <div className="space-y-1.5">
              {alerts.slice(0, 5).map((a) => (
                <div
                  key={a.id}
                  className="flex items-center justify-between gap-3 p-2 rounded bg-panel border border-borderSubtle text-[11px]"
                >
                  <div className="flex items-center gap-2 truncate">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase bg-red-500/20 text-red-300 border border-red-500/30">
                      {a.alert_type}
                    </span>
                    <span className="font-medium text-textPrimary truncate">{a.title}</span>
                  </div>
                  <span className="font-mono text-[10px] text-textSecondary whitespace-nowrap">
                    Impact: {a.impact_score.toFixed(0)}/100
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </header>
  );
}
