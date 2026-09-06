"use client";

import React from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  HelpCircle,
  Info,
  Shield,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Severity Badge (Never color alone — always paired with label)
// ---------------------------------------------------------------------------

export type SeverityLevel = "critical" | "high" | "moderate" | "low" | "info" | string;

export function SeverityBadge({
  severity,
  className = "",
  size = "md",
}: {
  severity: SeverityLevel;
  className?: string;
  size?: "sm" | "md";
}) {
  const norm = (severity || "info").toLowerCase();

  const config: Record<
    string,
    { label: string; bg: string; text: string; border: string; icon: React.ComponentType<{ className?: string }> }
  > = {
    critical: {
      label: "CRITICAL",
      bg: "bg-red-500/10",
      text: "text-red-400",
      border: "border-red-500/30",
      icon: AlertCircle,
    },
    high: {
      label: "HIGH",
      bg: "bg-orange-500/10",
      text: "text-orange-400",
      border: "border-orange-500/30",
      icon: AlertTriangle,
    },
    moderate: {
      label: "MODERATE",
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/30",
      icon: AlertTriangle,
    },
    low: {
      label: "LOW",
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/30",
      icon: Info,
    },
    info: {
      label: "INFO",
      bg: "bg-slate-500/10",
      text: "text-slate-400",
      border: "border-slate-500/30",
      icon: Info,
    },
  };

  const current = config[norm] || config.info;
  const Icon = current.icon;
  const sizeClasses =
    size === "sm"
      ? "text-[10px] px-1.5 py-0.5 gap-1"
      : "text-[11px] px-2 py-0.5 gap-1.5";

  return (
    <span
      className={`inline-flex items-center font-mono font-semibold rounded border uppercase tracking-wider ${current.bg} ${current.text} ${current.border} ${sizeClasses} ${className}`}
    >
      <Icon className={size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3"} />
      <span>{current.label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Verification Badge (Human-in-the-loop review state)
// ---------------------------------------------------------------------------

export type VerificationStatus = "verified" | "needs_review" | "pending" | "rejected" | "unverified" | string;

export function VerificationBadge({
  status,
  className = "",
  size = "md",
}: {
  status: VerificationStatus;
  className?: string;
  size?: "sm" | "md";
}) {
  const norm = (status || "unverified").toLowerCase();

  const config: Record<
    string,
    { label: string; bg: string; text: string; border: string; icon: React.ComponentType<{ className?: string }> }
  > = {
    verified: {
      label: "VERIFIED",
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/30",
      icon: ShieldCheck,
    },
    needs_review: {
      label: "NEEDS REVIEW",
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/30",
      icon: Clock,
    },
    pending: {
      label: "PENDING REVIEW",
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/30",
      icon: Clock,
    },
    rejected: {
      label: "REJECTED",
      bg: "bg-red-500/10",
      text: "text-red-400",
      border: "border-red-500/30",
      icon: XCircle,
    },
    unverified: {
      label: "UNVERIFIED",
      bg: "bg-slate-500/10",
      text: "text-slate-400",
      border: "border-slate-500/30",
      icon: HelpCircle,
    },
  };

  const current = config[norm] || config.unverified;
  const Icon = current.icon;
  const sizeClasses =
    size === "sm"
      ? "text-[10px] px-1.5 py-0.5 gap-1"
      : "text-[11px] px-2 py-0.5 gap-1.5";

  return (
    <span
      className={`inline-flex items-center font-mono font-semibold rounded border uppercase tracking-wider ${current.bg} ${current.text} ${current.border} ${sizeClasses} ${className}`}
    >
      <Icon className={size === "sm" ? "w-2.5 h-2.5" : "w-3 h-3"} />
      <span>{current.label}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Trust Badge (Algorithmically derived 0-100 score)
// ---------------------------------------------------------------------------

export function TrustBadge({
  score,
  className = "",
}: {
  score: number;
  className?: string;
}) {
  const val = Math.max(0, Math.min(100, Math.round(score)));
  let color = "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  let label = "HIGH TRUST";

  if (val < 45) {
    color = "text-red-400 bg-red-500/10 border-red-500/30";
    label = "LOW TRUST";
  } else if (val < 70) {
    color = "text-amber-400 bg-amber-500/10 border-amber-500/30";
    label = "MED TRUST";
  }

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[10px] font-semibold px-2 py-0.5 rounded border ${color} ${className}`}
      title={`Computed Trust Score: ${val}/100 (${label})`}
    >
      <Shield className="w-2.5 h-2.5" />
      <span>{val}%</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Live Status Indicator (Stream health)
// ---------------------------------------------------------------------------

export function LiveStatusIndicator({
  status = "LIVE",
  className = "",
}: {
  status?: "LIVE" | "PAUSED" | "RECONNECTING" | "OFFLINE";
  className?: string;
}) {
  const config = {
    LIVE: {
      color: "bg-live text-live",
      ping: "bg-live animate-ping",
      border: "border-live/30",
      text: "LIVE",
    },
    PAUSED: {
      color: "bg-amber-400 text-amber-400",
      ping: "",
      border: "border-amber-500/30",
      text: "PAUSED",
    },
    RECONNECTING: {
      color: "bg-yellow-400 text-yellow-400",
      ping: "bg-yellow-400 animate-pulse",
      border: "border-yellow-500/30",
      text: "RECONNECTING",
    },
    OFFLINE: {
      color: "bg-red-400 text-red-400",
      ping: "",
      border: "border-red-500/30",
      text: "OFFLINE",
    },
  }[status] || {
    color: "bg-slate-400 text-slate-400",
    ping: "",
    border: "border-slate-500/30",
    text: status,
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-panelRaised border ${config.border} ${className}`}
    >
      <span className="relative flex h-2 w-2">
        {config.ping && (
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${config.ping}`} />
        )}
        <span className={`relative inline-flex rounded-full h-2 w-2 ${config.color.split(" ")[0]}`} />
      </span>
      <span className={config.color.split(" ")[1]}>{config.text}</span>
    </span>
  );
}
