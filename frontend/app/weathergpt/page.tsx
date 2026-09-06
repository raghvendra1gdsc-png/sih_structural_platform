"use client";

import React, { useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CloudRain,
  CornerDownLeft,
  FileText,
  HelpCircle,
  Info,
  Layers,
  MessageSquareCode,
  Radio,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  Thermometer,
  User,
  Wind,
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "weathergpt";
  text: string;
  city?: string;
  citations?: string[];
  safetyNotice?: string | null;
  reasoningEngine?: string | null;
  structuredContext?: any;
  updatedAt?: string;
}

const SAMPLE_PROMPTS = [
  "Will it rain in Jodhpur tomorrow?",
  "Should I carry an umbrella in Jaipur today?",
  "What weather events are active near Jaipur?",
  "Will there be strong winds in Mumbai tonight?",
  "Is it safe to take a fishing boat out near Kochi tomorrow?",
  "What are the highest-impact regions right now?",
  "Is tomorrow morning suitable for travelling in Delhi?",
];

function renderInlineFormatting(str: string) {
  const parts = str.split(/(\*\*.*?\*\*|\[.*?\]\(.*?\))/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-textPrimary">
          {part.slice(2, -2)}
        </strong>
      );
    }
    const linkMatch = part.match(/^\[(.*?)\]\((.*?)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent underline hover:text-accent/80 transition-colors"
        >
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
}

function FormattedMessage({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1 text-xs leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }
        if (trimmed.startsWith("### ")) {
          return (
            <div
              key={idx}
              className="font-mono font-bold text-accent tracking-wide pt-2.5 pb-1 border-b border-borderSubtle/60 text-[12px] flex items-center gap-1.5"
            >
              {trimmed.replace("### ", "")}
            </div>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <div
              key={idx}
              className="font-mono font-bold text-textPrimary tracking-wide pt-2 pb-1 text-[13px]"
            >
              {trimmed.replace("## ", "")}
            </div>
          );
        }
        if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
          const content = trimmed.replace(/^[-•]\s*/, "");
          return (
            <div key={idx} className="flex items-start gap-2 pl-1 py-0.5 text-textPrimary">
              <span className="w-1.5 h-1.5 rounded-full bg-accent/70 mt-1.5 flex-shrink-0" />
              <div className="flex-1">{renderInlineFormatting(content)}</div>
            </div>
          );
        }
        return (
          <p key={idx} className="text-textPrimary py-0.5">
            {renderInlineFormatting(trimmed)}
          </p>
        );
      })}
    </div>
  );
}

export default function WeatherGPTPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "weathergpt",
      text: "Welcome to **WeatherGPT Decision Support**, the conversational intelligence copilot for the National Weather Big Data Analytics Platform.\n\nI generate grounded answers by synthesizing real-time **multi-provider numerical forecasts** (Open-Meteo, OpenWeather, Tomorrow.io, WeatherAPI) with **spatiotemporal PostGIS incident clusters**, **verified citizen observations**, and **platform impact scores**.",
      citations: [
        "Open-Meteo Numerical Forecast (Primary Provider)",
        "PostGIS Spatiotemporal DBSCAN Clustering Engine",
        "National Citizen & Sensor Ground Truth Database",
        "India Meteorological Department (IMD) Reference Baseline",
      ],
      reasoningEngine: "Gemini 3.6 Flash • Multi-Provider Grounded Chain",
      updatedAt: "Live Synchronized",
    },
  ]);

  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedCitationId, setExpandedCitationId] = useState<string | null>("welcome");

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSend = async (queryText: string) => {
    const q = queryText.trim();
    if (!q || loading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: q,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat/weathergpt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });

      if (res.ok) {
        const data = await res.json();
        const gptMsg: Message = {
          id: `gpt-${Date.now()}`,
          sender: "weathergpt",
          text: data.answer,
          city: data.city,
          citations: data.citations,
          safetyNotice: data.safety_notice,
          reasoningEngine: data.reasoning_engine,
          structuredContext: data.structured_context || data.evidence,
          updatedAt: data.updated_at,
        };
        setMessages((prev) => [...prev, gptMsg]);
        setExpandedCitationId(gptMsg.id);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            sender: "weathergpt",
            text: "WeatherGPT service encountered an error processing your query. Please verify backend service connectivity.",
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: "weathergpt",
          text: "WeatherGPT service is temporarily unreachable. Local forecast cache is still queryable directly via `/api/weather/current`.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6.5rem)] max-h-[900px] space-y-3">
      {/* Header Context Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-panel p-3.5 rounded-card border border-borderSubtle flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="font-display text-sm font-bold text-textPrimary tracking-wider uppercase">
              WEATHERGPT CONVERSATIONAL INTELLIGENCE
            </h2>
            <p className="text-[11px] text-textSecondary font-sans">
              Grounded meteorological reasoning backed by multi-provider consensus and PostGIS observations.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[10px] font-mono text-textSecondary">
          <span className="w-2 h-2 rounded-full bg-live animate-pulse" />
          <span>ZERO HALLUCINATIONS TOLERANCE • STRICT EVIDENCE BOUND</span>
        </div>
      </div>

      {/* Main Conversation Stream */}
      <div className="flex-1 bg-panel rounded-card border border-borderSubtle p-4 overflow-y-auto space-y-4">
        {messages.map((m) => {
          const isUser = m.sender === "user";
          return (
            <div
              key={m.id}
              className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto justify-end" : "mr-auto"}`}
            >
              {!isUser && (
                <div className="w-7 h-7 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent flex-shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5" />
                </div>
              )}

              <div className="space-y-2 max-w-2xl">
                <div
                  className={`p-3.5 rounded-card text-xs leading-relaxed ${
                    isUser
                      ? "bg-accent text-background font-semibold shadow-md whitespace-pre-line"
                      : "bg-panelRaised border border-borderSubtle text-textPrimary font-sans"
                  }`}
                >
                  {isUser ? m.text : <FormattedMessage text={m.text} />}
                </div>

                {/* Safety Advisory Banner if present */}
                {m.safetyNotice && (
                  <div className="p-2.5 rounded bg-red-500/10 border border-red-500/30 text-red-300 text-[11px] font-mono flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <span>{m.safetyNotice}</span>
                  </div>
                )}

                {/* Grounded Meteorological & Platform Evidence Box */}
                {!isUser && m.citations && m.citations.length > 0 && (
                  <div className="bg-panelRaised/70 border border-borderSubtle rounded p-2.5 text-[11px] font-mono">
                    <button
                      onClick={() =>
                        setExpandedCitationId(expandedCitationId === m.id ? null : m.id)
                      }
                      className="w-full flex items-center justify-between text-textSecondary hover:text-textPrimary transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <FileText className="w-3.5 h-3.5 text-accent" />
                        <span className="font-bold uppercase tracking-wider text-[10px]">
                          EVIDENCE & DATA GROUNDING ({m.citations.length} SOURCES)
                        </span>
                        {m.reasoningEngine && (
                          <span className="text-[9px] px-1.5 py-0.2 rounded bg-white/5 border border-borderSubtle text-textDisabled">
                            {m.reasoningEngine}
                          </span>
                        )}
                      </div>
                      {expandedCitationId === m.id ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </button>

                    {expandedCitationId === m.id && (
                      <div className="mt-2.5 pt-2 border-t border-borderSubtle/60 space-y-1.5 text-textSecondary">
                        {m.citations.map((c, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                            <span>{c}</span>
                          </div>
                        ))}

                        {m.structuredContext && (
                          <div className="mt-2 pt-2 border-t border-borderSubtle/40 grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
                            {m.structuredContext.current_temp_c !== undefined && (
                              <div className="p-1.5 rounded bg-panel border border-borderSubtle">
                                <span className="text-textDisabled">Observed Temp:</span>{" "}
                                <strong className="text-textPrimary">
                                  {m.structuredContext.current_temp_c.toFixed(1)}°C
                                </strong>
                              </div>
                            )}
                            {m.structuredContext.tomorrow_rain_prob !== undefined && (
                              <div className="p-1.5 rounded bg-panel border border-borderSubtle">
                                <span className="text-textDisabled">Rain Chance:</span>{" "}
                                <strong className="text-blue-400">
                                  {m.structuredContext.tomorrow_rain_prob}%
                                </strong>
                              </div>
                            )}
                            {m.structuredContext.aqi !== undefined && (
                              <div className="p-1.5 rounded bg-panel border border-borderSubtle">
                                <span className="text-textDisabled">AQI:</span>{" "}
                                <strong className={m.structuredContext.aqi > 100 ? "text-amber-400" : "text-accent"}>
                                  {m.structuredContext.aqi} ({m.structuredContext.aqi_category || "Moderate"})
                                </strong>
                              </div>
                            )}
                            {m.structuredContext.platform_impact_score !== undefined && (
                              <div className="p-1.5 rounded bg-panel border border-borderSubtle">
                                <span className="text-textDisabled">Impact Score:</span>{" "}
                                <strong className="text-red-400">
                                  {Math.round(m.structuredContext.platform_impact_score)}/100
                                </strong>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {isUser && (
                <div className="w-7 h-7 rounded bg-panelRaised border border-borderSubtle flex items-center justify-center text-textSecondary flex-shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3 max-w-lg">
            <div className="w-7 h-7 rounded bg-accent/20 border border-accent/40 flex items-center justify-center text-accent flex-shrink-0">
              <Bot className="w-3.5 h-3.5 animate-spin" />
            </div>
            <div className="p-3 rounded-card bg-panelRaised border border-borderSubtle text-xs font-mono text-textSecondary flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <span>Querying multi-provider consensus and PostGIS incident clusters...</span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Quick Inquiries */}
      <div className="flex items-center gap-1.5 overflow-x-auto py-1 px-1 text-[11px] font-mono text-textSecondary flex-shrink-0">
        <span className="text-[10px] text-textDisabled uppercase mr-1">QUICK PROMPTS:</span>
        {SAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => handleSend(p)}
            className="px-2.5 py-1 rounded bg-panelRaised border border-borderSubtle hover:border-borderStrong hover:text-textPrimary transition-colors whitespace-nowrap text-[10px]"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(inputQuery);
        }}
        className="flex gap-2 flex-shrink-0"
      >
        <input
          type="text"
          placeholder="Ask a meteorological or platform safety question across India (e.g. Will it rain in Jodhpur tomorrow?)..."
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          disabled={loading}
          className="flex-1 bg-panel text-xs text-textPrimary px-4 py-3 rounded-card border border-borderSubtle focus:border-accent focus:outline-none placeholder:text-textDisabled font-sans disabled:opacity-50"
        />

        <button
          type="submit"
          disabled={!inputQuery.trim() || loading}
          className="px-4 py-3 rounded-card bg-accent hover:bg-accent-hover text-white font-mono text-xs font-bold flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <span>SEND</span>
          <CornerDownLeft className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}
