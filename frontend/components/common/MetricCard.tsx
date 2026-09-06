"use client";

import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  icon?: React.ComponentType<{ className?: string }>;
  accentColor?: string;
  delta?: {
    value: string;
    isPositive?: boolean;
  };
  onClick?: () => void;
  className?: string;
}

export function MetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
  accentColor = "text-accent",
  delta,
  onClick,
  className = "",
}: MetricCardProps) {
  return (
    <div
      onClick={onClick}
      className={`bg-panel border border-borderSubtle rounded-card p-3.5 transition-all ${
        onClick ? "cursor-pointer hover:border-borderStrong hover:bg-panelRaised" : ""
      } ${className}`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[11px] font-mono uppercase tracking-wider text-textSecondary truncate">
          {label}
        </span>
        {Icon && <Icon className={`w-3.5 h-3.5 ${accentColor} flex-shrink-0`} />}
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <div className="font-mono text-2xl font-bold tracking-tight text-textPrimary tabular-nums">
          {value}
        </div>

        {delta && (
          <span
            className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded ${
              delta.isPositive
                ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
                : "text-amber-400 bg-amber-500/10 border border-amber-500/20"
            }`}
          >
            {delta.value}
          </span>
        )}
      </div>

      {sublabel && (
        <div className="text-[11px] text-textDisabled mt-1 truncate">
          {sublabel}
        </div>
      )}
    </div>
  );
}
