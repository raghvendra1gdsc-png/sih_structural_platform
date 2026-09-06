"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Flame,
  Info,
  MapPin,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
  Zap,
} from "lucide-react";
import { SeverityBadge } from "@/components/common/Badges";
import { Drawer } from "@/components/common/Drawer";
import { LoadingSkeleton, EmptyState } from "@/components/common/States";

const IndiaWeatherMap = dynamic(() => import("@/components/IndiaWeatherMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[480px] bg-panel rounded-card border border-borderSubtle flex items-center justify-center text-textSecondary text-xs font-mono">
      <RefreshCw className="w-4 h-4 animate-spin mr-2 text-red-400" />
      SYNCHRONIZING EARLY WARNING HOTSPOT RADAR...
    </div>
  ),
});

export default function EarlyWarningPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchEarlyWarningData = async (isInitial: boolean = false) => {
    try {
      if (isInitial) setLoading(true);
      const [resAlerts, resHotspots, resInc] = await Promise.all([
        fetch(`${API_URL}/api/alerts`),
        fetch(`${API_URL}/api/map/hotspots`),
        fetch(`${API_URL}/api/incidents?limit=50`),
      ]);

      if (resAlerts.ok) {
        const d = await resAlerts.json();
        setAlerts(d || []);
        if (d && d.length > 0 && !selectedAlert) {
          setSelectedAlert(d[0]);
        }
      }
      if (resHotspots.ok) setHotspots(await resHotspots.json());
      if (resInc.ok) {
        const d = await resInc.json();
        setIncidents(d.items || []);
      }
    } catch (err) {
      console.error("Early warning fetch failed:", err);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchEarlyWarningData(true);
    // Real-time live polling every 5s with zero delay
    const interval = setInterval(() => {
      fetchEarlyWarningData(false);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-4">
      {/* Mandatory Official Disclaimer Banner */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-card p-3 flex items-start gap-3 text-amber-300">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-400 mt-0.5" />
        <div className="space-y-0.5 text-xs font-mono">
          <div className="font-bold tracking-wider uppercase">
            PLATFORM-ASSISTED EARLY DETECTION — NOT AN OFFICIAL IMD WARNING
          </div>
          <p className="text-[11px] text-amber-200/80 font-sans leading-relaxed">
            All early escalation signals are algorithmically derived from citizen report clustering, AI classification, and numerical weather model consensus. Always verify with official bulletins from the <strong>India Meteorological Department (mausam.imd.gov.in)</strong> before initiating civil protection measures.
          </p>
        </div>
      </div>

      {/* Main Grid: Emerging Events List (4 cols) + Hotspot Map (8 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Emerging Escalations Queue */}
        <div className="lg:col-span-4 bg-panel border border-borderSubtle rounded-card p-3.5 flex flex-col h-[640px]">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-borderSubtle">
            <span className="font-mono text-xs font-bold text-textPrimary tracking-wide flex items-center gap-2">
              <Flame className="w-3.5 h-3.5 text-red-400" />
              ACTIVE ESCALATIONS ({alerts.length})
            </span>
            <span className="text-[10px] font-mono text-textSecondary">IMPACT ≥ 50</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {loading ? (
              <LoadingSkeleton rows={6} />
            ) : alerts.length === 0 ? (
              <EmptyState
                title="No Emerging Anomalies"
                description="The platform has not detected rapid report surges or high-impact weather escalations."
              />
            ) : (
              alerts.map((al) => (
                <div
                  key={al.id}
                  onClick={() => setSelectedAlert(al)}
                  className={`p-3 rounded border transition-all cursor-pointer ${
                    selectedAlert?.id === al.id
                      ? "bg-panelHighlight border-red-500/50 shadow-md"
                      : "bg-panelRaised/60 border-borderSubtle hover:border-borderStrong hover:bg-panelRaised"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1 font-mono text-[10px]">
                    <span className="px-1.5 py-0.2 rounded font-bold uppercase bg-red-500/20 text-red-300 border border-red-500/30">
                      {al.alert_type}
                    </span>
                    <span className="text-textSecondary">
                      {al.timestamp ? new Date(al.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Active"}
                    </span>
                  </div>

                  <h3 className="font-semibold text-xs text-textPrimary truncate mt-1">
                    {al.title}
                  </h3>

                  <p className="text-[11px] text-textSecondary line-clamp-2 mt-1 leading-relaxed">
                    {al.message}
                  </p>

                  <div className="flex items-center justify-between pt-2 mt-2 border-t border-borderSubtle/60 text-[10px] font-mono">
                    <span className="text-textPrimary">{al.city}, {al.state}</span>
                    <span className="font-bold text-red-400">
                      Impact: {Math.round(al.impact_score)}/100
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: Hotspot Map & Evidence Panel */}
        <div className="lg:col-span-8 flex flex-col gap-4 h-[640px]">
          {/* Hotspot Radar Map */}
          <div className="flex-1 min-h-[360px]">
            <IndiaWeatherMap
              incidents={incidents}
              onSelectIncident={(inc) => {
                const matched = alerts.find((a) => a.city.toLowerCase() === inc.city.toLowerCase());
                if (matched) setSelectedAlert(matched);
              }}
            />
          </div>

          {/* Selected Escalation Detail Card */}
          {selectedAlert && (
            <div className="bg-panel border border-borderSubtle rounded-card p-4 flex-shrink-0">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-borderSubtle">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                  <span className="font-mono text-xs font-bold text-textPrimary uppercase">
                    {selectedAlert.title}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-red-400 font-bold bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded">
                  PLATFORM IMPACT: {Math.round(selectedAlert.impact_score)} / 100
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs font-mono">
                <div className="md:col-span-2 text-textSecondary font-sans text-xs leading-relaxed bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
                  {selectedAlert.message}
                </div>

                <div className="space-y-1.5">
                  <div className="bg-panelRaised/60 p-2 rounded border border-borderSubtle flex justify-between">
                    <span className="text-textSecondary">Target City:</span>
                    <span className="text-textPrimary font-bold">{selectedAlert.city}</span>
                  </div>
                  <div className="bg-panelRaised/60 p-2 rounded border border-borderSubtle flex justify-between">
                    <span className="text-textSecondary">Severity:</span>
                    <SeverityBadge severity={selectedAlert.severity} size="sm" />
                  </div>
                  <a
                    href={`/live-weather?city=${encodeURIComponent(selectedAlert.city)}`}
                    className="block w-full py-1.5 rounded bg-accent/15 border border-accent/30 text-accent font-mono text-[11px] font-bold text-center hover:bg-accent/25 transition-colors"
                  >
                    INVESTIGATE RADAR
                  </a>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
