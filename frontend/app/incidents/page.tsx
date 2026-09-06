"use client";

import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Filter,
  Layers,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { SeverityBadge } from "@/components/common/Badges";
import { Drawer } from "@/components/common/Drawer";
import { LoadingSkeleton, EmptyState, ErrorState } from "@/components/common/States";

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);

  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [reclustering, setReclustering] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchIncidents = async (isInitial: boolean = false) => {
    try {
      if (isInitial) setLoading(true);
      let url = `${API_URL}/api/incidents?limit=100`;
      if (categoryFilter) url += `&category=${categoryFilter}`;
      if (severityFilter) url += `&severity=${severityFilter}`;
      if (searchQuery) url += `&city=${encodeURIComponent(searchQuery)}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setIncidents(data.items || []);
        setTotal(data.total || 0);
      }
    } catch (err) {
      console.error("Incidents fetch error:", err);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents(true);
    // Real-time live polling every 5s (zero delay)
    const interval = setInterval(() => {
      fetchIncidents(false);
    }, 5000);
    return () => clearInterval(interval);
  }, [categoryFilter, severityFilter, searchQuery]);

  const handleTriggerRecluster = async () => {
    try {
      setReclustering(true);
      const res = await fetch(`${API_URL}/api/incidents/recluster`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setToastMessage(`Spatiotemporal re-clustering complete (${data.incidents_created || 0} clusters synced)`);
        fetchIncidents();
      }
    } catch (e) {
      setToastMessage("Reclustering failed to sync with PostGIS.");
    } finally {
      setReclustering(false);
      setTimeout(() => setToastMessage(null), 4000);
    }
  };

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-panel p-4 rounded-card border border-borderSubtle">
        <div>
          <h2 className="font-mono text-sm font-bold tracking-tight text-textPrimary uppercase flex items-center gap-2">
            <Layers className="w-4 h-4 text-accent" />
            OPERATIONAL INCIDENT MANAGEMENT CONSOLE
          </h2>
          <p className="text-[11px] text-textSecondary mt-0.5 font-sans">
            Spatiotemporal DBSCAN clusters of multi-source citizen observations and meteorological anomalies.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {toastMessage && (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded animate-fadeIn">
              {toastMessage}
            </span>
          )}

          <button
            onClick={handleTriggerRecluster}
            disabled={reclustering}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/15 border border-accent/40 text-accent hover:bg-accent/25 font-mono text-xs font-bold transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reclustering ? "animate-spin" : ""}`} />
            <span>RE-CLUSTER POSTGIS</span>
          </button>
        </div>
      </div>

      {/* Filter Ribbon */}
      <div className="flex flex-wrap items-center gap-2 bg-panelRaised/40 p-2.5 rounded border border-borderSubtle">
        <div className="flex items-center gap-1.5 bg-panel px-2.5 py-1 rounded border border-borderSubtle flex-1 min-w-[180px]">
          <Search className="w-3.5 h-3.5 text-textDisabled" />
          <input
            type="text"
            placeholder="Search by city or district..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent text-xs text-textPrimary placeholder:text-textDisabled focus:outline-none w-full font-mono"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-panel text-xs text-textPrimary px-2.5 py-1.5 rounded border border-borderSubtle font-mono focus:outline-none"
        >
          <option value="">ALL CATEGORIES</option>
          <option value="rainfall">Rainfall</option>
          <option value="flooding">Flooding</option>
          <option value="thunderstorm">Thunderstorm</option>
          <option value="heatwave">Heatwave</option>
          <option value="cyclone">Cyclone</option>
          <option value="dust_storm">Dust Storm</option>
          <option value="hailstorm">Hailstorm</option>
          <option value="fog">Fog</option>
        </select>

        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-panel text-xs text-textPrimary px-2.5 py-1.5 rounded border border-borderSubtle font-mono focus:outline-none"
        >
          <option value="">ALL SEVERITIES</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="moderate">Moderate</option>
          <option value="low">Low</option>
        </select>

        <span className="text-[11px] font-mono text-textSecondary ml-auto px-2">
          TOTAL CLUSTERS: <strong className="text-textPrimary">{total}</strong>
        </span>
      </div>

      {/* Incident Operational Data Table */}
      <div className="bg-panel rounded-card border border-borderSubtle overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-borderSubtle bg-panelRaised/70 font-mono text-[10px] text-textSecondary uppercase tracking-wider">
                <th className="py-2.5 px-4 font-bold">SECTOR / CITY</th>
                <th className="py-2.5 px-3 font-bold">CATEGORY</th>
                <th className="py-2.5 px-3 font-bold">SEVERITY</th>
                <th className="py-2.5 px-3 font-bold text-right">IMPACT SCORE</th>
                <th className="py-2.5 px-3 font-bold text-center">REPORTS</th>
                <th className="py-2.5 px-3 font-bold text-center">VERIFIED</th>
                <th className="py-2.5 px-3 font-bold text-right">RADIUS</th>
                <th className="py-2.5 px-4 text-center">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderSubtle/60 text-xs font-mono">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-6">
                    <LoadingSkeleton rows={5} />
                  </td>
                </tr>
              ) : incidents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8">
                    <EmptyState
                      title="No Incident Clusters Found"
                      description="No weather clusters match the current category, severity, or search query."
                    />
                  </td>
                </tr>
              ) : (
                incidents.map((inc) => (
                  <tr
                    key={inc.incident_id}
                    onClick={() => setSelectedIncident(inc)}
                    className="hover:bg-white/[0.03] transition-colors cursor-pointer group"
                  >
                    <td className="py-2.5 px-4 font-semibold text-textPrimary">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-textDisabled group-hover:text-accent" />
                        <span>{inc.city}, {inc.state}</span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-textSecondary uppercase text-[11px]">
                      {inc.event_category}
                    </td>
                    <td className="py-2.5 px-3">
                      <SeverityBadge severity={inc.severity} size="sm" />
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={`font-bold px-1.5 py-0.5 rounded text-[11px] ${
                          inc.impact_score >= 70
                            ? "bg-red-500/15 text-red-400 border border-red-500/30"
                            : inc.impact_score >= 45
                            ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                            : "bg-accent/15 text-accent border border-accent/30"
                        }`}
                      >
                        {Math.round(inc.impact_score)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center text-textPrimary font-semibold">
                      {inc.report_count}
                    </td>
                    <td className="py-2.5 px-3 text-center text-emerald-400 font-semibold">
                      {inc.verified_count}
                    </td>
                    <td className="py-2.5 px-3 text-right text-textSecondary text-[11px]">
                      {inc.radius_km} km
                    </td>
                    <td className="py-2.5 px-4 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedIncident(inc);
                        }}
                        className="p-1 rounded text-textDisabled hover:text-accent hover:bg-white/5 transition-colors"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Incident Deep Inspector Drawer */}
      <Drawer
        isOpen={Boolean(selectedIncident)}
        onClose={() => setSelectedIncident(null)}
        title={selectedIncident ? `${selectedIncident.city}, ${selectedIncident.state}` : ""}
        subtitle={selectedIncident ? `INCIDENT UUID: ${selectedIncident.incident_id}` : ""}
        badge={
          selectedIncident ? (
            <SeverityBadge severity={selectedIncident.severity} size="sm" />
          ) : undefined
        }
      >
        {selectedIncident && (
          <div className="space-y-4">
            {/* KPI Banner */}
            <div className="bg-panelRaised p-3 rounded border border-borderStrong flex items-center justify-between font-mono">
              <div>
                <span className="text-[10px] text-textSecondary uppercase">Impact Score</span>
                <div className="text-2xl font-bold text-textPrimary">
                  {Math.round(selectedIncident.impact_score)} / 100
                </div>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-textSecondary uppercase">Spread Radius</span>
                <div className="text-lg font-bold text-live">{selectedIncident.radius_km} km</div>
              </div>
            </div>

            {/* Meteorological Narrative Summary */}
            <div className="space-y-1">
              <span className="font-mono text-[10px] font-bold text-textSecondary uppercase tracking-wider">
                Automated Incident Summary
              </span>
              <p className="text-xs text-textPrimary bg-panelRaised/40 p-3 rounded border border-borderSubtle leading-relaxed">
                {selectedIncident.summary ||
                  `Active ${selectedIncident.event_category} cluster identified within municipal limits based on spatiotemporal concentration of citizen reports.`}
              </p>
            </div>

            {/* Geolocation & Report Volume Breakdown */}
            <div className="space-y-1 font-mono text-[11px]">
              <span className="text-[10px] font-bold text-textSecondary uppercase tracking-wider">
                Geospatial Coordinates
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-panelRaised/60 p-2 rounded border border-borderSubtle">
                  <span className="text-textSecondary">Latitude:</span>
                  <div className="text-textPrimary">{selectedIncident.latitude?.toFixed(4)}° N</div>
                </div>
                <div className="bg-panelRaised/60 p-2 rounded border border-borderSubtle">
                  <span className="text-textSecondary">Longitude:</span>
                  <div className="text-textPrimary">{selectedIncident.longitude?.toFixed(4)}° E</div>
                </div>
              </div>
            </div>

            {/* Direct Link to Live Weather Workspace */}
            <div className="pt-3 border-t border-borderSubtle">
              <a
                href={`/live-weather?city=${encodeURIComponent(selectedIncident.city)}`}
                className="w-full py-2.5 rounded bg-accent/20 border border-accent/40 text-accent font-mono text-xs font-bold text-center block hover:bg-accent/30 transition-colors"
              >
                OPEN RADAR & METEOROLOGICAL HUD
              </a>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
