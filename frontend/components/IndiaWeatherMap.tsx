"use client";

import React, { useEffect, useRef, useState } from "react";
import { Layers, MapPin, Shield } from "lucide-react";

export interface MapIncident {
  incident_id: string;
  city: string;
  state: string;
  event_category: string;
  report_count: number;
  verified_count: number;
  severity: string;
  impact_score: number;
  latitude: number;
  longitude: number;
  radius_km: number;
  summary?: string;
}

export interface MapReport {
  report_id: string;
  city: string;
  state?: string;
  latitude: number;
  longitude: number;
  event_category: string;
  source_trust_score: number;
  verification_status: string;
  text?: string;
}

interface IndiaWeatherMapProps {
  incidents: MapIncident[];
  reports?: MapReport[];
  selectedCity?: string | null;
  onSelectIncident?: (incident: MapIncident) => void;
  onSelectReport?: (report: MapReport) => void;
  className?: string;
}

export default function IndiaWeatherMap({
  incidents,
  reports = [],
  selectedCity,
  onSelectIncident,
  onSelectReport,
  className = "",
}: IndiaWeatherMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const baseTileLayerRef = useRef<any>(null);
  const incidentsLayerRef = useRef<any>(null);
  const reportsLayerRef = useRef<any>(null);

  const [showIncidents, setShowIncidents] = useState<boolean>(true);
  const [showReports, setShowReports] = useState<boolean>(true);
  const [mapStyle, setMapStyle] = useState<"dark" | "voyager" | "satellite">("dark");

  const cartoKey = process.env.NEXT_PUBLIC_CARTO_API_KEY || "cb1_2yru_1_be975c21c3c99af922bcf25c";

  const getTileConfig = (style: "dark" | "voyager" | "satellite") => {
    if (style === "voyager") {
      return {
        url: `https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=${cartoKey}&api_key=${cartoKey}`,
        options: {
          attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
          subdomains: "abcd",
          maxZoom: 20,
        },
      };
    }
    if (style === "satellite") {
      return {
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        options: {
          attribution: '&copy; <a href="https://www.esri.com/">Esri</a> Satellite',
          maxZoom: 18,
        },
      };
    }
    // Default: CARTO Dark All (Watermark-free: CARTO CDN strictly mandates ?key= parameter)
    return {
      url: `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${cartoKey}&api_key=${cartoKey}`,
      options: {
        attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> | SIH 2026',
        subdomains: "abcd",
        maxZoom: 20,
      },
    };
  };

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    let isMounted = true;

    import("leaflet").then((L) => {
      if (!isMounted || !mapContainerRef.current) return;

      const map = L.map(mapContainerRef.current, {
        center: [22.0, 79.5],
        zoom: 4.8,
        minZoom: 4,
        maxZoom: 16,
        zoomControl: false,
      });

      L.control.zoom({ position: "topright" }).addTo(map);

      // Fit complete Indian Subcontinent bounds: Kashmir to Kanyakumari, Gujarat to Arunachal Pradesh
      const indiaBounds: [[number, number], [number, number]] = [
        [7.8, 68.0],
        [36.5, 97.5],
      ];
      map.fitBounds(indiaBounds, { padding: [10, 10] });

      // Add verified CARTO basemap
      const cfg = getTileConfig("dark");
      const baseLayer = L.tileLayer(cfg.url, cfg.options).addTo(map);
      baseTileLayerRef.current = baseLayer;

      incidentsLayerRef.current = L.layerGroup().addTo(map);
      reportsLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;

      // Invalidate size to guarantee crisp rendering without clipping
      setTimeout(() => {
        if (isMounted && map) {
          map.invalidateSize();
        }
      }, 200);
    });

    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update base tile layer on style toggle
  useEffect(() => {
    if (!mapInstanceRef.current || !baseTileLayerRef.current) return;
    import("leaflet").then((L) => {
      if (!mapInstanceRef.current) return;
      mapInstanceRef.current.removeLayer(baseTileLayerRef.current);
      const cfg = getTileConfig(mapStyle);
      const newLayer = L.tileLayer(cfg.url, cfg.options).addTo(mapInstanceRef.current);
      baseTileLayerRef.current = newLayer;
      newLayer.bringToBack();
    });
  }, [mapStyle]);

  // Update layer visibility
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    if (incidentsLayerRef.current) {
      if (showIncidents) {
        if (!mapInstanceRef.current.hasLayer(incidentsLayerRef.current)) {
          mapInstanceRef.current.addLayer(incidentsLayerRef.current);
        }
      } else {
        if (mapInstanceRef.current.hasLayer(incidentsLayerRef.current)) {
          mapInstanceRef.current.removeLayer(incidentsLayerRef.current);
        }
      }
    }
    if (reportsLayerRef.current) {
      if (showReports) {
        if (!mapInstanceRef.current.hasLayer(reportsLayerRef.current)) {
          mapInstanceRef.current.addLayer(reportsLayerRef.current);
        }
      } else {
        if (mapInstanceRef.current.hasLayer(reportsLayerRef.current)) {
          mapInstanceRef.current.removeLayer(reportsLayerRef.current);
        }
      }
    }
  }, [showIncidents, showReports]);

  // Render markers
  useEffect(() => {
    if (!mapInstanceRef.current) return;

    import("leaflet").then((L) => {
      // 1. Render Reports Layer
      if (reportsLayerRef.current) {
        reportsLayerRef.current.clearLayers();
        reports.slice(0, 200).forEach((rep) => {
          const isVerified = rep.verification_status === "verified";
          const dot = L.circleMarker([rep.latitude, rep.longitude], {
            radius: 3.5,
            color: isVerified ? "#10B981" : "#34D399",
            fillColor: isVerified ? "#10B981" : "#059669",
            fillOpacity: 0.6,
            weight: 1,
          });

          dot.bindTooltip(
            `<div class="text-[11px] font-mono leading-tight">
              <strong style="color: #E8EAED;">${rep.city}</strong>: <span style="color: #10B981;">${rep.event_category}</span>
              <br/><span style="color: #9AA3AE;">Trust: ${Math.round(rep.source_trust_score)}% • ${rep.verification_status.toUpperCase()}</span>
             </div>`,
            { className: "custom-leaflet-tooltip" }
          );

          if (onSelectReport) {
            dot.on("click", () => onSelectReport(rep));
          }

          reportsLayerRef.current.addLayer(dot);
        });
      }

      // 2. Render Incident Clusters Layer
      if (incidentsLayerRef.current) {
        incidentsLayerRef.current.clearLayers();
        incidents.forEach((inc) => {
          const isCritical = inc.impact_score >= 70;
          const isModerate = inc.impact_score >= 45;
          const color = isCritical ? "#EF4444" : isModerate ? "#F5B400" : "#10B981";

          // Spread perimeter
          const radiusMeters = Math.max(3000, (inc.radius_km || 5.0) * 1000);
          const circle = L.circle([inc.latitude, inc.longitude], {
            radius: radiusMeters,
            color: color,
            fillColor: color,
            fillOpacity: isCritical ? 0.22 : 0.12,
            weight: isCritical ? 1.5 : 1,
            dashArray: isCritical ? undefined : "3, 5",
          });

          // Hotspot center icon
          const marker = L.circleMarker([inc.latitude, inc.longitude], {
            radius: isCritical ? 8 : 6,
            color: "#FFFFFF",
            fillColor: color,
            fillOpacity: 0.95,
            weight: 1.5,
          });

          const popupContent = `
            <div style="font-family: 'Inter', sans-serif; font-size: 11px; min-width: 220px;">
              <div style="font-size: 13px; font-weight: 700; color: #E8EAED; margin-bottom: 3px; display: flex; justify-content: space-between; align-items: center;">
                <span>${inc.city}, ${inc.state}</span>
                <span style="font-family: 'JetBrains Mono', monospace; color: ${color}; font-size: 11px; padding: 2px 6px; background: rgba(0,0,0,0.5); border: 1px solid ${color}40; border-radius: 4px;">
                  ${Math.round(inc.impact_score)}/100
                </span>
              </div>
              <div style="font-family: 'JetBrains Mono', monospace; color: #9AA3AE; font-size: 10px; margin-bottom: 6px; text-transform: uppercase;">
                ${inc.event_category} • ${inc.severity} IMPACT
              </div>
              <div style="color: #CBD5E1; font-size: 11px; margin-bottom: 8px; line-height: 1.3;">
                ${inc.summary || "Active weather cluster identified across region."}
              </div>
              <div style="border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px; display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #9AA3AE;">
                <span>REPORTS: <strong style="color: #E8EAED;">${inc.report_count}</strong></span>
                <span>VERIFIED: <strong style="color: #22C55E;">${inc.verified_count}</strong></span>
                <span>ZONE: <strong style="color: #E8EAED;">${inc.radius_km}km</strong></span>
              </div>
            </div>
          `;

          marker.bindPopup(popupContent);
          circle.bindPopup(popupContent);

          if (onSelectIncident) {
            marker.on("click", () => onSelectIncident(inc));
          }

          incidentsLayerRef.current.addLayer(circle);
          incidentsLayerRef.current.addLayer(marker);
        });
      }
    });
  }, [incidents, reports, onSelectIncident, onSelectReport]);

  return (
    <div
      className={`relative w-full h-full min-h-[460px] rounded-card overflow-hidden border border-borderSubtle bg-background shadow-xl ${className}`}
    >
      <div ref={mapContainerRef} className="w-full h-full z-10" />

      {/* Top Left Status & Layer Controls */}
      <div className="absolute top-3 left-3 z-20 flex flex-wrap items-center gap-2">
        <div className="bg-panel/90 backdrop-blur-md border border-borderSubtle rounded px-2.5 py-1 text-[11px] font-mono text-textPrimary shadow flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-bold">{incidents.length} ACTIVE CLUSTERS</span>
        </div>

        <div className="bg-panel/90 backdrop-blur-md border border-borderSubtle rounded p-1 flex items-center gap-1 text-[10px] font-mono shadow">
          <button
            onClick={() => setShowIncidents(!showIncidents)}
            className={`px-2 py-0.5 rounded transition-colors ${
              showIncidents
                ? "bg-accent/20 text-accent border border-accent/30 font-semibold"
                : "text-textDisabled hover:text-textSecondary"
            }`}
          >
            CLUSTERS
          </button>
          <button
            onClick={() => setShowReports(!showReports)}
            className={`px-2 py-0.5 rounded transition-colors ${
              showReports
                ? "bg-live/20 text-live border border-live/30 font-semibold"
                : "text-textDisabled hover:text-textSecondary"
            }`}
          >
            REPORTS ({reports.length})
          </button>
        </div>

        {/* Basemap Switcher */}
        <div className="bg-panel/90 backdrop-blur-md border border-borderSubtle rounded p-1 flex items-center gap-1 text-[10px] font-mono shadow">
          <span className="text-textDisabled px-1 font-bold uppercase hidden sm:inline">MAP:</span>
          <button
            onClick={() => setMapStyle("dark")}
            className={`px-2 py-0.5 rounded transition-colors ${
              mapStyle === "dark"
                ? "bg-accent text-background font-bold"
                : "text-textDisabled hover:text-textSecondary"
            }`}
          >
            CARTO DARK
          </button>
          <button
            onClick={() => setMapStyle("voyager")}
            className={`px-2 py-0.5 rounded transition-colors ${
              mapStyle === "voyager"
                ? "bg-accent text-background font-bold"
                : "text-textDisabled hover:text-textSecondary"
            }`}
          >
            VOYAGER
          </button>
          <button
            onClick={() => setMapStyle("satellite")}
            className={`px-2 py-0.5 rounded transition-colors ${
              mapStyle === "satellite"
                ? "bg-accent text-background font-bold"
                : "text-textDisabled hover:text-textSecondary"
            }`}
          >
            SATELLITE
          </button>
        </div>
      </div>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-3 right-3 z-20 bg-panel/90 backdrop-blur-md border border-borderSubtle rounded p-2.5 shadow-xl text-[10px] font-mono pointer-events-auto max-w-[210px]">
        <div className="text-[10px] font-bold text-textSecondary uppercase tracking-wider mb-1.5 pb-1 border-b border-borderSubtle">
          GEOSPATIAL IMPACT LEGEND
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between text-textPrimary">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-500 shadow-sm shadow-red-500/50" />
              <span>Critical Impact</span>
            </div>
            <span className="text-textSecondary">70–100</span>
          </div>
          <div className="flex items-center justify-between text-textPrimary">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
              <span>Moderate Alert</span>
            </div>
            <span className="text-textSecondary">45–69</span>
          </div>
          <div className="flex items-center justify-between text-textPrimary">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent shadow-sm shadow-accent/50" />
              <span>Advisory Watch</span>
            </div>
            <span className="text-textSecondary">&lt;45</span>
          </div>
          <div className="flex items-center gap-1.5 pt-1 border-t border-borderSubtle text-textSecondary">
            <span className="w-1.5 h-1.5 rounded-full bg-live" />
            <span>Citizen / News Observation</span>
          </div>
        </div>
      </div>
    </div>
  );
}
