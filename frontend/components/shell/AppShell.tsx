"use client";

import React from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface AppShellProps {
  children: React.ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  isDemoMode?: boolean;
}

export function AppShell({
  children,
  onRefresh,
  refreshing = false,
  isDemoMode = false,
}: AppShellProps) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-transparent text-textPrimary">
      {/* Persistent Operations Sidebar */}
      <Sidebar />

      {/* Main Operational Stage */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar
          onRefresh={onRefresh}
          refreshing={refreshing}
          isDemoMode={isDemoMode}
        />

        <main className="flex-1 overflow-y-auto p-4 sm:p-5 lg:p-6 space-y-6">
          {children}
        </main>
      </div>
    </div>
  );
}
