"use client";

import React from "react";
import { AlertTriangle, Database, RefreshCw } from "lucide-react";

export function LoadingSkeleton({
  rows = 4,
  className = "",
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-2.5 animate-pulse ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-9 bg-panelRaised/70 rounded border border-borderSubtle/40"
        />
      ))}
    </div>
  );
}

export function EmptyState({
  title = "No Records Available",
  description = "No active records match the selected operational filters.",
  icon: Icon = Database,
  action,
  className = "",
}: {
  title?: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center bg-panel/50 rounded-card border border-borderSubtle ${className}`}
    >
      <div className="w-10 h-10 rounded-full bg-white/5 border border-borderSubtle flex items-center justify-center text-textSecondary mb-3">
        <Icon className="w-5 h-5" />
      </div>
      <h4 className="text-xs font-semibold text-textPrimary uppercase tracking-wider mb-1">
        {title}
      </h4>
      <p className="text-[11px] text-textSecondary max-w-sm mb-4 leading-relaxed">
        {description}
      </p>
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Telemetry Stream Disconnected",
  description = "Unable to communicate with the National Weather Platform backend services.",
  onRetry,
  className = "",
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-6 text-center bg-red-500/5 rounded-card border border-red-500/20 ${className}`}
    >
      <AlertTriangle className="w-6 h-6 text-red-400 mb-2" />
      <h4 className="text-xs font-mono font-bold text-red-400 uppercase tracking-wider mb-1">
        {title}
      </h4>
      <p className="text-[11px] text-textSecondary max-w-sm mb-3">{description}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-panelRaised border border-borderStrong text-textPrimary text-xs hover:bg-panelHighlight transition-colors"
        >
          <RefreshCw className="w-3 h-3 text-accent" />
          <span>Retry Connection</span>
        </button>
      )}
    </div>
  );
}
