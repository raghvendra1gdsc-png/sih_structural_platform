"use client";

import React, { useEffect } from "react";
import { X } from "lucide-react";

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: "md" | "lg" | "xl";
}

export function Drawer({
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  children,
  footer,
  width = "md",
}: DrawerProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const widthClass = {
    md: "sm:w-[440px]",
    lg: "sm:w-[560px]",
    xl: "sm:w-[680px]",
  }[width];

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Semi-transparent backdrop */}
      <div
        onClick={onClose}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
      />

      <div className="fixed inset-y-0 right-0 flex max-w-full pl-6">
        <div
          className={`w-screen ${widthClass} bg-panel border-l border-borderStrong shadow-2xl flex flex-col transform transition-transform duration-200 ease-out`}
        >
          {/* Drawer Header */}
          <div className="px-5 py-4 border-b border-borderSubtle flex items-start justify-between bg-panelRaised/60">
            <div className="space-y-1 pr-4">
              <div className="flex items-center gap-2">
                {badge}
                <div className="text-sm font-semibold text-textPrimary tracking-tight">
                  {title}
                </div>
              </div>
              {subtitle && (
                <p className="text-[11px] font-mono text-textSecondary">{subtitle}</p>
              )}
            </div>

            <button
              onClick={onClose}
              className="p-1 rounded text-textSecondary hover:text-textPrimary hover:bg-white/5 transition-colors"
              aria-label="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Drawer Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs text-textPrimary">
            {children}
          </div>

          {/* Optional Footer */}
          {footer && (
            <div className="p-4 border-t border-borderSubtle bg-panelRaised/40 flex items-center justify-end gap-2">
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
