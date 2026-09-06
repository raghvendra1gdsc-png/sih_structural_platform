"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  ExternalLink,
  GitMerge,
  History,
  Info,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { SeverityBadge, TrustBadge, VerificationBadge } from "@/components/common/Badges";
import { LoadingSkeleton, EmptyState } from "@/components/common/States";

export default function VerificationPage() {
  const [pendingReports, setPendingReports] = useState<any[]>([]);
  const [selectedReport, setSelectedReport] = useState<any | null>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionReason, setActionReason] = useState<string>("");
  const [canonicalIdInput, setCanonicalIdInput] = useState<string>("");
  const [showMergeInput, setShowMergeInput] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchPending = async (isInitial: boolean = false) => {
    try {
      if (isInitial) setLoading(true);
      const [resReports, resAudits] = await Promise.all([
        fetch(`${API_URL}/api/admin/reports/pending?limit=50`),
        fetch(`${API_URL}/api/admin/audits?limit=25`),
      ]);

      if (resReports.ok) {
        const data = await resReports.json();
        const items = data.items || [];
        setPendingReports(items);
        if (items.length > 0 && !selectedReport) {
          setSelectedReport(items[0]);
        }
      }

      if (resAudits.ok) {
        setAuditLogs(await resAudits.json());
      }
    } catch (err) {
      console.error("Verification fetch error:", err);
    } finally {
      if (isInitial) setLoading(false);
    }
  };

  useEffect(() => {
    fetchPending(true);
    // Real-time verification queue polling every 5s
    const interval = setInterval(() => {
      fetchPending(false);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleAction = async (status: string) => {
    if (!selectedReport) return;
    setIsProcessing(true);
    try {
      const res = await fetch(
        `${API_URL}/api/admin/reports/${selectedReport.report_id}/verification`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: status,
            reason: actionReason || `Admin flagged as ${status}`,
            reviewer: "Duty_Meteorologist_01",
          }),
        }
      );

      if (res.ok) {
        setToastMessage(`Report successfully marked as ${status.toUpperCase()}`);
        setActionReason("");
        // Remove verified report from pending queue
        const updated = pendingReports.filter((r) => r.report_id !== selectedReport.report_id);
        setPendingReports(updated);
        setSelectedReport(updated.length > 0 ? updated[0] : null);

        // Refresh audit trail
        const resAud = await fetch(`${API_URL}/api/admin/audits?limit=25`);
        if (resAud.ok) setAuditLogs(await resAud.json());
      } else {
        alert("Failed to submit verification action to backend.");
      }
    } catch (err) {
      console.error("Verification action error:", err);
    } finally {
      setIsProcessing(false);
      setTimeout(() => setToastMessage(null), 4000);
    }
  };

  const handleMerge = async () => {
    if (!selectedReport || !canonicalIdInput.trim()) return;
    setIsProcessing(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/reports/${selectedReport.report_id}/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          canonical_report_id: canonicalIdInput.trim(),
          reason: actionReason || "Merged near-duplicate into primary canonical record",
        }),
      });

      if (res.ok) {
        setToastMessage("Report successfully merged into canonical record.");
        setActionReason("");
        setCanonicalIdInput("");
        setShowMergeInput(false);

        const updated = pendingReports.filter((r) => r.report_id !== selectedReport.report_id);
        setPendingReports(updated);
        setSelectedReport(updated.length > 0 ? updated[0] : null);

        const resAud = await fetch(`${API_URL}/api/admin/audits?limit=25`);
        if (resAud.ok) setAuditLogs(await resAud.json());
      } else {
        alert("Merge failed. Verify the canonical UUID exists.");
      }
    } catch (err) {
      console.error("Merge error:", err);
    } finally {
      setIsProcessing(false);
      setTimeout(() => setToastMessage(null), 4000);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-panel p-4 rounded-card border border-borderSubtle">
        <div>
          <h2 className="font-mono text-sm font-bold tracking-tight text-textPrimary uppercase flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            HUMAN-IN-THE-LOOP VERIFICATION WORKSPACE
          </h2>
          <p className="text-[11px] text-textSecondary mt-0.5 font-sans">
            Triage pending citizen observations, validate AI classifications, and manage duplicate merges.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {toastMessage && (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 rounded animate-fadeIn">
              {toastMessage}
            </span>
          )}
          <button
            onClick={fetchPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-panelRaised border border-borderSubtle hover:bg-white/5 text-textSecondary hover:text-textPrimary font-mono text-xs transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-accent" />
            <span>REFRESH QUEUE</span>
          </button>
        </div>
      </div>

      {/* 3-Zone Moderation Station */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Zone 1: Pending Queue (4 cols) */}
        <div className="lg:col-span-4 bg-panel border border-borderSubtle rounded-card p-3.5 flex flex-col h-[660px]">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-borderSubtle font-mono text-xs">
            <span className="font-bold text-textPrimary uppercase flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              PENDING QUEUE ({pendingReports.length})
            </span>
            <span className="text-[10px] text-textSecondary">FIFO ORDER</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {loading ? (
              <LoadingSkeleton rows={6} />
            ) : pendingReports.length === 0 ? (
              <EmptyState
                title="Moderation Queue Clear"
                description="Zero pending reports require review at this time. All observations triaged."
              />
            ) : (
              pendingReports.map((rep) => (
                <div
                  key={rep.report_id}
                  onClick={() => setSelectedReport(rep)}
                  className={`p-3 rounded border transition-all cursor-pointer ${
                    selectedReport?.report_id === rep.report_id
                      ? "bg-panelHighlight border-accent shadow-md"
                      : "bg-panelRaised/50 border-borderSubtle hover:border-borderStrong hover:bg-panelRaised"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 mb-1 font-mono text-[10px]">
                    <span className="font-semibold text-textPrimary">{rep.city}, {rep.state}</span>
                    <span className="text-textDisabled uppercase">{rep.source}</span>
                  </div>

                  <p className="text-xs text-textSecondary line-clamp-2 leading-relaxed">
                    {rep.text || `Weather anomaly observed: ${rep.event_category}`}
                  </p>

                  <div className="flex items-center justify-between pt-2 mt-1 border-t border-borderSubtle/60 text-[10px] font-mono">
                    <span className="text-accent uppercase font-bold">{rep.event_category}</span>
                    <TrustBadge score={rep.source_trust_score} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Zone 2 & 3: Deep Inspector & Action Panel (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-4 h-[660px]">
          {selectedReport ? (
            <div className="bg-panel border border-borderSubtle rounded-card p-4 flex-1 flex flex-col justify-between overflow-y-auto">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between pb-3 border-b border-borderSubtle">
                  <div>
                    <h3 className="font-mono text-base font-bold text-textPrimary">
                      {selectedReport.city}, {selectedReport.state}
                    </h3>
                    <span className="font-mono text-[10px] text-textSecondary">
                      UUID: {selectedReport.report_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <TrustBadge score={selectedReport.source_trust_score} />
                    <VerificationBadge status={selectedReport.verification_status} />
                  </div>
                </div>

                {/* Observation Text */}
                <div className="space-y-1">
                  <span className="font-mono text-[10px] font-bold text-textSecondary uppercase tracking-wider">
                    CITIZEN / SOURCE OBSERVATION TEXT
                  </span>
                  <div className="bg-panelRaised/80 p-3.5 rounded border border-borderSubtle text-textPrimary text-xs leading-relaxed font-sans">
                    {selectedReport.text || "No description provided."}
                  </div>
                </div>

                {/* Telemetry Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-xs">
                  <div className="bg-panelRaised/40 p-2 rounded border border-borderSubtle">
                    <span className="text-[10px] text-textSecondary uppercase">Source Channel</span>
                    <div className="text-textPrimary font-bold uppercase mt-0.5">{selectedReport.source}</div>
                  </div>
                  <div className="bg-panelRaised/40 p-2 rounded border border-borderSubtle">
                    <span className="text-[10px] text-textSecondary uppercase">AI Classification</span>
                    <div className="text-accent font-bold uppercase mt-0.5">{selectedReport.event_category}</div>
                  </div>
                  <div className="bg-panelRaised/40 p-2 rounded border border-borderSubtle">
                    <span className="text-[10px] text-textSecondary uppercase">AI Confidence</span>
                    <div className="text-textPrimary font-bold mt-0.5">
                      {Math.round((selectedReport.event_confidence || 0.85) * 100)}%
                    </div>
                  </div>
                  <div className="bg-panelRaised/40 p-2 rounded border border-borderSubtle">
                    <span className="text-[10px] text-textSecondary uppercase">Coordinates</span>
                    <div className="text-textPrimary font-bold mt-0.5 text-[10px]">
                      {selectedReport.latitude?.toFixed(2)}°N, {selectedReport.longitude?.toFixed(2)}°E
                    </div>
                  </div>
                </div>

                {/* Optional Reviewer Reason Input */}
                <div className="space-y-1 font-mono">
                  <span className="text-[10px] font-bold text-textSecondary uppercase tracking-wider">
                    VERIFICATION DECISION NOTES (AUDIT TRAIL LOGGED)
                  </span>
                  <input
                    type="text"
                    placeholder="Enter reason for decision (e.g. Ground station validated, Duplicate, False report)..."
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    className="w-full bg-panelRaised text-xs text-textPrimary p-2.5 rounded border border-borderSubtle focus:border-accent focus:outline-none"
                  />
                </div>

                {/* Merge UI if toggled */}
                {showMergeInput && (
                  <div className="p-3 bg-panelRaised border border-amber-500/30 rounded space-y-2 font-mono text-xs">
                    <span className="text-[10px] font-bold text-amber-300 uppercase">
                      ENTER CANONICAL REPORT UUID TO MERGE INTO:
                    </span>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Target report UUID..."
                        value={canonicalIdInput}
                        onChange={(e) => setCanonicalIdInput(e.target.value)}
                        className="flex-1 bg-background text-xs text-textPrimary p-2 rounded border border-borderSubtle focus:outline-none"
                      />
                      <button
                        onClick={handleMerge}
                        disabled={isProcessing}
                        className="px-3 py-1.5 bg-amber-500 text-black font-bold rounded text-xs hover:bg-amber-400 transition-colors"
                      >
                        CONFIRM MERGE
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons Toolbar */}
              <div className="pt-3 border-t border-borderSubtle flex flex-wrap items-center gap-2 font-mono text-xs">
                <button
                  onClick={() => handleAction("verified")}
                  disabled={isProcessing}
                  className="flex-1 py-2.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-bold hover:bg-emerald-500/30 flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                  <span>VERIFY REPORT</span>
                </button>

                <button
                  onClick={() => handleAction("needs_review")}
                  disabled={isProcessing}
                  className="flex-1 py-2.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-400 font-bold hover:bg-amber-500/30 flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <Clock className="w-4 h-4" />
                  <span>NEEDS REVIEW</span>
                </button>

                <button
                  onClick={() => handleAction("rejected")}
                  disabled={isProcessing}
                  className="flex-1 py-2.5 rounded bg-red-500/20 border border-red-500/40 text-red-400 font-bold hover:bg-red-500/30 flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                >
                  <X className="w-4 h-4" />
                  <span>REJECT REPORT</span>
                </button>

                <button
                  onClick={() => setShowMergeInput(!showMergeInput)}
                  disabled={isProcessing}
                  className="px-3 py-2.5 rounded bg-panelRaised border border-borderSubtle text-textSecondary hover:text-textPrimary hover:bg-white/5 flex items-center gap-1.5 transition-colors"
                >
                  <GitMerge className="w-4 h-4" />
                  <span>MERGE</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-panel border border-borderSubtle rounded-card p-8 flex items-center justify-center flex-1 text-center">
              <EmptyState
                title="Select a Report"
                description="Choose an observation from the pending queue to inspect details and record moderation actions."
              />
            </div>
          )}

          {/* Audit History Log Table */}
          <div className="bg-panel border border-borderSubtle rounded-card p-3 h-48 overflow-hidden flex flex-col font-mono">
            <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-borderSubtle text-[11px]">
              <span className="font-bold text-textPrimary uppercase flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-accent" />
                VERIFICATION AUDIT TRAIL
              </span>
              <span className="text-textSecondary text-[10px]">Non-Repudiable Logs</span>
            </div>

            <div className="overflow-y-auto flex-1 text-[10px]">
              <table className="w-full text-left border-collapse">
                <thead className="border-b border-borderSubtle text-textSecondary">
                  <tr>
                    <th className="py-1 px-2">TIME</th>
                    <th className="py-1 px-2">REPORT</th>
                    <th className="py-1 px-2">ACTION</th>
                    <th className="py-1 px-2">REVIEWER</th>
                    <th className="py-1 px-2">REASON</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borderSubtle/50 text-textSecondary">
                  {auditLogs.slice(0, 10).map((log) => (
                    <tr key={log.id}>
                      <td className="py-1 px-2 text-textDisabled">
                        {log.created_at ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recently"}
                      </td>
                      <td className="py-1 px-2 text-textPrimary font-semibold">
                        {log.report_id?.slice(0, 8)}...
                      </td>
                      <td className="py-1 px-2 uppercase font-bold text-emerald-400">
                        {log.new_status || log.action}
                      </td>
                      <td className="py-1 px-2 text-textSecondary">{log.reviewer}</td>
                      <td className="py-1 px-2 truncate max-w-[150px] text-textDisabled">{log.reason || "--"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
