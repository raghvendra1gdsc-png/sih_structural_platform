"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  Filter,
  Layers,
  MapPin,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
} from "lucide-react";
import { LiveStatusIndicator, SeverityBadge, TrustBadge, VerificationBadge } from "@/components/common/Badges";
import { Drawer } from "@/components/common/Drawer";
import { LoadingSkeleton, EmptyState } from "@/components/common/States";

export default function LiveFeedPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [selectedReport, setSelectedReport] = useState<any | null>(null);

  const [streamState, setStreamState] = useState<"LIVE" | "PAUSED" | "RECONNECTING" | "OFFLINE">("LIVE");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [onlyCanonical, setOnlyCanonical] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchReports = async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      let url = `${API_URL}/api/reports?limit=50&only_canonical=${onlyCanonical}`;
      if (categoryFilter) url += `&category=${categoryFilter}`;
      if (sourceFilter) url += `&source=${sourceFilter}`;
      if (searchQuery) url += `&city=${encodeURIComponent(searchQuery)}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setReports(data.items || []);
        setTotal(data.total || 0);
        if (streamState === "RECONNECTING") setStreamState("LIVE");
      } else {
        setStreamState("RECONNECTING");
      }
    } catch (err) {
      console.error("Feed error:", err);
      setStreamState("OFFLINE");
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports(true);
  }, [categoryFilter, sourceFilter, onlyCanonical, searchQuery]);

  // Live polling stream
  useEffect(() => {
    // Live polling stream every 3s (real-time zero delay)
    const interval = setInterval(() => {
      fetchReports(false);
    }, 3000);
    return () => clearInterval(interval);
  }, [streamState, categoryFilter, sourceFilter, onlyCanonical, searchQuery]);

  return (
    <div className="space-y-4">
      {/* Header with Stream Health Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-panel p-4 rounded-card border border-borderSubtle">
        <div>
          <h2 className="font-mono text-sm font-bold tracking-tight text-textPrimary uppercase flex items-center gap-2">
            <Radio className="w-4 h-4 text-live" />
            REAL-TIME MULTI-SOURCE INGESTION STREAM
          </h2>
          <p className="text-[11px] text-textSecondary mt-0.5 font-sans">
            Continuous ingestion pipeline receiving observations across citizen apps, GDELT 2.0, and Reddit.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <LiveStatusIndicator status={streamState} />

          <button
            onClick={() => setStreamState(streamState === "LIVE" ? "PAUSED" : "LIVE")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded font-mono text-xs font-bold transition-colors ${
              streamState === "LIVE"
                ? "bg-panelRaised border border-borderSubtle text-textSecondary hover:text-textPrimary"
                : "bg-live/20 border border-live/40 text-live"
            }`}
          >
            {streamState === "LIVE" ? (
              <>
                <Pause className="w-3.5 h-3.5 text-amber-400" />
                <span>PAUSE STREAM</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 text-live" />
                <span>RESUME LIVE</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Filter Ribbon */}
      <div className="flex flex-wrap items-center gap-2 bg-panelRaised/40 p-2.5 rounded border border-borderSubtle text-xs font-mono">
        <div className="flex items-center gap-1.5 bg-panel px-2.5 py-1 rounded border border-borderSubtle flex-1 min-w-[180px]">
          <Search className="w-3.5 h-3.5 text-textDisabled" />
          <input
            type="text"
            placeholder="Search report text or city..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-xs text-textPrimary placeholder:text-textDisabled focus:outline-none w-full font-mono"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-panel text-xs text-textPrimary px-2.5 py-1.5 rounded border border-borderSubtle focus:outline-none"
        >
          <option value="">ALL CATEGORIES</option>
          <option value="rainfall">Rainfall</option>
          <option value="flooding">Flooding</option>
          <option value="thunderstorm">Thunderstorm</option>
          <option value="heatwave">Heatwave</option>
          <option value="cyclone">Cyclone</option>
          <option value="dust_storm">Dust Storm</option>
        </select>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="bg-panel text-xs text-textPrimary px-2.5 py-1.5 rounded border border-borderSubtle focus:outline-none"
        >
          <option value="">ALL SOURCES</option>
          <option value="citizen">Citizen App</option>
          <option value="gdelt">GDELT News</option>
          <option value="reddit">Reddit (r/india)</option>
          <option value="weather_api">Weather API</option>
        </select>

        <label className="flex items-center gap-2 text-textSecondary cursor-pointer px-2">
          <input
            type="checkbox"
            checked={onlyCanonical}
            onChange={(e) => setOnlyCanonical(e.target.checked)}
            className="rounded bg-panel border-borderSubtle text-accent focus:ring-0"
          />
          <span>Exclude Collapsed Duplicates</span>
        </label>

        <span className="text-[11px] text-textSecondary ml-auto px-2">
          REPORTS IN QUEUE: <strong className="text-textPrimary">{total}</strong>
        </span>
      </div>

      {/* Dense Operational Stream Table */}
      <div className="bg-panel rounded-card border border-borderSubtle overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-borderSubtle bg-panelRaised/70 font-mono text-[10px] text-textSecondary uppercase tracking-wider">
                <th className="py-2.5 px-4 font-bold">TIMESTAMP</th>
                <th className="py-2.5 px-3 font-bold">SOURCE</th>
                <th className="py-2.5 px-4 font-bold">SECTOR / CITY</th>
                <th className="py-2.5 px-3 font-bold">AI CLASSIFICATION</th>
                <th className="py-2.5 px-3 font-bold text-center">CONFIDENCE</th>
                <th className="py-2.5 px-3 font-bold text-center">TRUST SCORE</th>
                <th className="py-2.5 px-3 font-bold text-center">VERIFICATION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderSubtle/60 text-xs font-mono">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-6">
                    <LoadingSkeleton rows={8} />
                  </td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8">
                    <EmptyState
                      title="No Reports Received"
                      description="No incoming weather reports match the active filters."
                    />
                  </td>
                </tr>
              ) : (
                reports.map((rep) => (
                  <tr
                    key={rep.report_id}
                    onClick={() => setSelectedReport(rep)}
                    className="hover:bg-white/[0.03] transition-colors cursor-pointer"
                  >
                    <td className="py-2.5 px-4 text-textSecondary text-[11px]">
                      {rep.event_time
                        ? new Date(rep.event_time).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })
                        : "Just Now"}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-panelRaised border border-borderSubtle text-accent">
                        {rep.source}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-textPrimary">
                      {rep.city}, {rep.state}
                    </td>
                    <td className="py-2.5 px-3 text-textPrimary uppercase text-[11px]">
                      {rep.event_category}
                    </td>
                    <td className="py-2.5 px-3 text-center text-textSecondary">
                      {Math.round((rep.event_confidence || 0.85) * 100)}%
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <TrustBadge score={rep.source_trust_score} />
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <VerificationBadge status={rep.verification_status} size="sm" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Report Contextual Deep Drawer */}
      <Drawer
        isOpen={Boolean(selectedReport)}
        onClose={() => setSelectedReport(null)}
        title={selectedReport ? `${selectedReport.city}, ${selectedReport.state}` : ""}
        subtitle={selectedReport ? `REPORT ID: ${selectedReport.report_id}` : ""}
        badge={
          selectedReport ? (
            <VerificationBadge status={selectedReport.verification_status} size="sm" />
          ) : undefined
        }
      >
        {selectedReport && (
          <div className="space-y-4">
            {/* Raw Observation Content */}
            <div className="space-y-1">
              <span className="font-mono text-[10px] font-bold text-textSecondary uppercase tracking-wider">
                Raw Observation Narrative
              </span>
              <div className="bg-panelRaised/60 p-3 rounded border border-borderSubtle text-textPrimary text-xs leading-relaxed font-sans">
                {selectedReport.text || "No observational text supplied with record."}
              </div>
            </div>

            {/* AI Classification & Trust Telemetry */}
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div className="bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
                <span className="text-[10px] text-textSecondary uppercase">AI Event Category</span>
                <div className="font-bold text-accent uppercase text-sm mt-0.5">
                  {selectedReport.event_category}
                </div>
              </div>

              <div className="bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
                <span className="text-[10px] text-textSecondary uppercase">Trust Score</span>
                <div className="font-bold text-emerald-400 text-sm mt-0.5">
                  {Math.round(selectedReport.source_trust_score)} / 100
                </div>
              </div>

              <div className="bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
                <span className="text-[10px] text-textSecondary uppercase">Source Channel</span>
                <div className="font-bold text-textPrimary uppercase mt-0.5">
                  {selectedReport.source}
                </div>
              </div>

              <div className="bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
                <span className="text-[10px] text-textSecondary uppercase">Canonical Status</span>
                <div className="font-bold text-textPrimary mt-0.5">
                  {selectedReport.duplicate_of ? "Near-Duplicate" : "Primary Record"}
                </div>
              </div>
            </div>

            {/* Coordinates */}
            <div className="p-2.5 bg-panelRaised/40 rounded border border-borderSubtle text-[11px] font-mono flex items-center justify-between">
              <span className="text-textSecondary">Coordinates:</span>
              <span className="text-textPrimary">
                {selectedReport.latitude?.toFixed(4)}° N, {selectedReport.longitude?.toFixed(4)}° E
              </span>
            </div>

            {/* Link to Admin Verification */}
            <div className="pt-2 border-t border-borderSubtle">
              <a
                href="/verification"
                className="block w-full py-2 rounded bg-accent/20 border border-accent/40 text-accent font-mono text-xs font-bold text-center hover:bg-accent/30 transition-colors"
              >
                OPEN VERIFICATION STATION
              </a>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
