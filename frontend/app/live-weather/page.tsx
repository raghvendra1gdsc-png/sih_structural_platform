"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Cloud,
  CloudDrizzle,
  CloudFog,
  CloudLightning,
  CloudRain,
  CloudSnow,
  CloudSun,
  Compass,
  Droplets,
  Eye,
  Gauge,
  MapPin,
  Moon,
  Radio,
  Search,
  Shield,
  Sun,
  Sunrise,
  Sunset,
  Thermometer,
  ThermometerSnowflake,
  ThermometerSun,
  Wind,
} from "lucide-react";

const CITIES = [
  "Jaipur",
  "New Delhi",
  "Mumbai",
  "Chennai",
  "Kolkata",
  "Bengaluru",
  "Shimla",
  "Bhubaneswar",
];

function HomeAssistantWeatherDashboard() {
  const searchParams = useSearchParams();
  const initialCity = searchParams.get("city") || "Jaipur";

  const [selectedCity, setSelectedCity] = useState<string>(initialCity);
  const [currentWeather, setCurrentWeather] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Digital Clock state
  const [currentTime, setCurrentTime] = useState({
    timeStr: "10:37",
    dateStr: "Wed, 18/01/2023",
  });

  const radarMapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const hours = now.getHours().toString().padStart(2, "0");
      const minutes = now.getMinutes().toString().padStart(2, "0");
      const day = now.toLocaleDateString("en-GB", { weekday: "short" });
      const d = now.getDate().toString().padStart(2, "0");
      const m = (now.getMonth() + 1).toString().padStart(2, "0");
      const y = now.getFullYear();

      setCurrentTime({
        timeStr: `${hours}:${minutes}`,
        dateStr: `${day}, ${d}/${m}/${y}`,
      });
    };

    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchCityWeatherData = async (city: string) => {
    try {
      setLoading(true);
      const [resCur, resFore, resComp, resAlerts] = await Promise.all([
        fetch(`${API_URL}/api/weather/current?city=${encodeURIComponent(city)}`),
        fetch(`${API_URL}/api/weather/forecast?city=${encodeURIComponent(city)}`),
        fetch(`${API_URL}/api/weather/comparison?city=${encodeURIComponent(city)}`),
        fetch(`${API_URL}/api/alerts`),
      ]);

      if (resCur.ok) setCurrentWeather(await resCur.json());
      if (resFore.ok) setForecast(await resFore.json());
      if (resComp.ok) setComparison(await resComp.json());
      if (resAlerts.ok) setAlerts(await resAlerts.json());
    } catch (err) {
      console.error("Home Assistant weather fetch failed:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCityWeatherData(selectedCity);
  }, [selectedCity]);

  // Initialize Radar Map
  useEffect(() => {
    if (!radarMapRef.current) return;
    if (mapInstanceRef.current) return;

    let isMounted = true;
    import("leaflet").then((L) => {
      if (!isMounted || !radarMapRef.current) return;

      const lat = currentWeather?.latitude || 26.9124;
      const lon = currentWeather?.longitude || 75.7873;

      const map = L.map(radarMapRef.current, {
        center: [lat, lon],
        zoom: 7,
        zoomControl: false,
        attributionControl: false,
      });

      // Dark Carto Basemap layer with user API key (?key= parameter)
      const cartoKey = process.env.NEXT_PUBLIC_CARTO_API_KEY || "cb1_2yru_1_be975c21c3c99af922bcf25c";
      L.tileLayer(
        `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=${cartoKey}&api_key=${cartoKey}`,
        {
          subdomains: "abcd",
          maxZoom: 18,
          attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OSM',
        }
      ).addTo(map);

      // Radar pulse ring on location
      L.circle([lat, lon], {
        radius: 45000,
        color: "#34D399",
        fillColor: "#34D399",
        fillOpacity: 0.15,
        weight: 1.5,
      }).addTo(map);

      L.circle([lat, lon], {
        radius: 12000,
        color: "#10B981",
        fillColor: "#10B981",
        fillOpacity: 0.35,
        weight: 1.5,
      }).addTo(map);

      L.circleMarker([lat, lon], {
        radius: 4,
        color: "#FFFFFF",
        fillColor: "#34D399",
        fillOpacity: 1,
        weight: 1.5,
      }).addTo(map);

      mapInstanceRef.current = map;
    });

    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [currentWeather]);

  // Derived Values
  const tempC = currentWeather?.temperature_c !== undefined ? currentWeather.temperature_c : -0.4;
  const condition = currentWeather?.condition_text || "Partly cloudy";
  const rainMm = currentWeather?.precipitation_mm !== undefined ? currentWeather.precipitation_mm : 5.7;
  const windKmh = currentWeather?.wind_kmh !== undefined ? currentWeather.wind_kmh : 5.7;
  const humidity = currentWeather?.humidity_pct !== undefined ? currentWeather.humidity_pct : 87;
  const pressure = currentWeather?.pressure_hpa !== undefined ? currentWeather.pressure_hpa : 948;

  // 5-Day forecast items
  const dailyForecast =
    forecast?.daily && forecast.daily.length >= 5
      ? forecast.daily.slice(0, 5).map((d: any, idx: number) => {
          const days = ["Thu", "Fri", "Sat", "Sun", "Mon"];
          return {
            day: d.date ? new Date(d.date).toLocaleDateString("en-US", { weekday: "short" }) : days[idx],
            high: d.temp_max_c ? d.temp_max_c.toFixed(1) : (5.0 - idx * 1.2).toFixed(1),
            low: d.temp_min_c ? d.temp_min_c.toFixed(1) : (-0.8 - idx * 1.1).toFixed(1),
            rain: d.precipitation_mm ? d.precipitation_mm.toFixed(1) : (0.3).toFixed(1),
            condition: d.condition || "Partly cloudy",
          };
        })
      : [
          { day: "Thu", high: "5.0", low: "-0.8", rain: "0.3", condition: "Partly cloudy" },
          { day: "Fri", high: "3.6", low: "-0.8", rain: "0.0", condition: "Partly cloudy" },
          { day: "Sat", high: "3.1", low: "-2.9", rain: "0.0", condition: "Sunny" },
          { day: "Sun", high: "0.1", low: "-4.3", rain: "0.0", condition: "Partly cloudy" },
          { day: "Mon", high: "0.1", low: "-5.7", rain: "0.4", condition: "Snow" },
        ];

  // Active early warning advisory
  const activeWarning = alerts.length > 0 ? alerts[0] : null;

  return (
    <div className="space-y-4 max-w-[1720px] mx-auto pb-10">
      {/* Target City Sector Bar */}
      <div className="flex items-center justify-between bg-[#192A21]/70 backdrop-blur-md p-2.5 rounded-xl border border-white/10">
        <div className="flex items-center gap-2 overflow-x-auto text-xs">
          <MapPin className="w-4 h-4 text-[#34D399] flex-shrink-0" />
          <span className="font-mono text-[#98B5A5] text-[11px] uppercase tracking-wider mr-1">
            Sector:
          </span>
          {CITIES.map((c) => (
            <button
              key={c}
              onClick={() => setSelectedCity(c)}
              className={`px-3 py-1 rounded-lg text-xs transition-all whitespace-nowrap ${
                selectedCity.toLowerCase() === c.toLowerCase()
                  ? "bg-[#34D399] text-[#12211A] font-bold shadow-md shadow-[#34D399]/20"
                  : "bg-[#21362B] text-[#98B5A5] hover:text-white border border-white/5"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="hidden sm:flex items-center gap-2 font-mono text-[11px] text-[#98B5A5]">
          <span>INTELLIGENCE SOURCE:</span>
          <span className="text-[#34D399] font-bold">HOME ASSISTANT ECOSYSTEM</span>
        </div>
      </div>

      {/* EXACT 4-COLUMN WEATHER DASHBOARD GRID */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-start font-sans">
        
        {/* ========================================================================= */}
        {/* COLUMN 1: Weather Forecast Card + Weather Radar Card                      */}
        {/* ========================================================================= */}
        <div className="space-y-4">
          {/* Card 1A: Weather Forecast Card by Home Assistant */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Weather Forecast Card</span>
              <span className="text-[10px] text-[#98B5A5]">by Home Assistant</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg text-white space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative flex-shrink-0">
                    <Sun className="w-10 h-10 text-amber-400 drop-shadow" />
                    <Cloud className="w-8 h-8 text-slate-200 fill-slate-300 absolute -bottom-1 -right-1" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-white tracking-tight leading-snug">
                      {condition}
                    </div>
                    <div className="text-xs text-[#98B5A5]">Weather</div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-2xl font-bold text-white tracking-tight">
                    {tempC > 0 ? `${tempC.toFixed(1)} °C` : `${tempC.toFixed(1)} °C`}
                  </div>
                  <div className="flex items-center justify-end gap-1 text-xs text-[#98B5A5] mt-0.5">
                    <Droplets className="w-3 h-3 text-[#34D399]" />
                    <span>{rainMm} mm</span>
                  </div>
                </div>
              </div>

              {/* 5-Day forecast row */}
              <div className="grid grid-cols-5 gap-1 pt-3 border-t border-white/10 text-center">
                {dailyForecast.map((d, i) => (
                  <div key={i} className="space-y-1">
                    <div className="text-[11px] text-white/80 font-medium">{d.day}</div>
                    <div className="flex justify-center my-0.5">
                      {i === 2 ? (
                        <Sun className="w-4 h-4 text-amber-400" />
                      ) : (
                        <Cloud className="w-4 h-4 text-slate-300" />
                      )}
                    </div>
                    <div className="text-xs font-semibold text-white">{d.high}°</div>
                    <div className="text-[10px] text-[#98B5A5]">{d.low}°</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Card 1B: Weather Radar Card by Makin-Things */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Weather Radar Card</span>
              <span className="text-[10px] text-[#98B5A5]">by Makin-Things</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] overflow-hidden border border-white/10 shadow-lg relative h-[360px] flex flex-col justify-between">
              {/* Radar Doppler Spectrum gradient bar across top */}
              <div className="h-1.5 w-full bg-gradient-to-r from-purple-500 via-pink-500 via-blue-500 via-emerald-400 via-yellow-400 to-red-500 z-10" />

              {/* Leaflet Satellite Map */}
              <div ref={radarMapRef} className="w-full flex-1 z-0" />

              {/* Timestamp & Attribution Banner */}
              <div className="bg-[#12211A]/90 backdrop-blur-md px-3 py-1.5 text-[9px] text-[#98B5A5] font-mono flex items-center justify-between border-t border-white/5 z-10">
                <span>Wed Jan 18 10:20</span>
                <span>Radar data by RainViewer</span>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* COLUMN 2: Simple Weather + Clock Weather + Weather Conditions             */}
        {/* ========================================================================= */}
        <div className="space-y-4">
          {/* Card 2A: Simple Weather Card by kalkih */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Simple Weather Card</span>
              <span className="text-[10px] text-[#98B5A5]">by kalkih</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-3.5 border border-white/10 shadow-lg space-y-2.5 text-xs text-white">
              {/* Row 1 */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-amber-400/20 flex items-center justify-center text-amber-400">
                    <Sun className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="font-semibold text-white">{tempC.toFixed(1)} °C Forecast Home</div>
                    <div className="text-[10px] text-[#98B5A5]">{condition}</div>
                  </div>
                </div>
                <div className="text-right text-[11px] text-[#98B5A5]">
                  <div>-0.8 °C / 5 °C</div>
                  <div className="flex items-center justify-end gap-1 text-[10px]">
                    <Droplets className="w-2.5 h-2.5 text-[#34D399]" />
                    <span>5.7 mm</span>
                  </div>
                </div>
              </div>

              {/* Row 2 */}
              <div className="flex items-center justify-between pt-2 border-t border-white/5">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-amber-400/20 flex items-center justify-center text-amber-400">
                    <Sun className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <div className="font-semibold text-white">{tempC.toFixed(1)} °C Home</div>
                    <div className="text-[10px] text-[#98B5A5]">{condition}</div>
                  </div>
                </div>
                <div className="text-right text-[11px] text-[#98B5A5]">
                  <div className="flex items-center justify-end gap-1.5">
                    <span>SSW</span>
                    <span>87 %</span>
                  </div>
                  <div className="flex items-center justify-end gap-1.5 text-[10px]">
                    <span>5.7 mm</span>
                    <span>0 %</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2B: Clock Weather Card by pkissling */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Clock Weather Card</span>
              <span className="text-[10px] text-[#98B5A5]">by pkissling</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-4">
              <div className="flex items-center justify-between">
                <div className="relative">
                  <Sun className="w-12 h-12 text-amber-400" />
                  <Cloud className="w-10 h-10 text-white fill-white absolute -bottom-1 -right-2 drop-shadow" />
                </div>

                <div className="text-right">
                  <div className="text-xs text-[#98B5A5]">Partly cloudy, 0°C</div>
                  <div className="text-4xl font-bold text-white tracking-tight leading-none mt-0.5">
                    {currentTime.timeStr}
                  </div>
                  <div className="text-xs text-[#98B5A5] mt-1">{currentTime.dateStr}</div>
                </div>
              </div>

              {/* 5 Horizontal Temperature Range Bars */}
              <div className="space-y-2 pt-2 border-t border-white/5 text-xs">
                {dailyForecast.map((d, i) => (
                  <div key={i} className="flex items-center justify-between text-[#98B5A5]">
                    <span className="w-7 text-[11px] font-medium text-white/90">{d.day}</span>
                    <Droplets className="w-3 h-3 text-[#34D399]" />
                    <span className="text-[10px] w-8 text-right">{d.low}°C</span>
                    {/* Horizontal Range Capsule */}
                    <div className="flex-1 mx-2.5 h-2 rounded-full bg-[#12211A] overflow-hidden relative">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#5bc0be] to-[#34d399]"
                        style={{
                          width: `${Math.max(30, 80 - i * 10)}%`,
                          marginLeft: `${i * 8}%`,
                        }}
                      />
                    </div>
                    <span className="text-[10px] w-8 text-left text-white font-medium">{d.high}°C</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Card 2C: Weather Conditions Card by r-renato */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Weather Conditions Card</span>
              <span className="text-[10px] text-[#98B5A5]">by r-renato</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-full bg-slate-300 flex items-center justify-center text-slate-800">
                    <Moon className="w-3.5 h-3.5 fill-slate-800" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-white">Home</div>
                    <div className="text-[10px] text-[#98B5A5]">Waning Crescent</div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-3xl font-bold text-white tracking-tight">1.1 °C</div>
                  <div className="text-[10px] text-[#98B5A5]">Feels Like 1 °C</div>
                </div>
              </div>

              {/* 2-Column Telemetry */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 pt-2 border-t border-white/5 text-[11px] text-[#98B5A5]">
                <div className="flex items-center justify-between">
                  <span>0% / 0 mm/h</span>
                  <Droplets className="w-3 h-3 text-[#34D399]" />
                </div>
                <div className="flex items-center justify-between">
                  <span>1 / 1 °C</span>
                  <Thermometer className="w-3 h-3 text-[#34D399]" />
                </div>

                <div className="flex items-center justify-between">
                  <span>948 hPa</span>
                  <Gauge className="w-3 h-3 text-[#34D399]" />
                </div>
                <div className="flex items-center justify-between">
                  <span>98 %</span>
                  <Droplets className="w-3 h-3 text-[#34D399]" />
                </div>

                <div className="flex items-center justify-between">
                  <span>0 km</span>
                  <Eye className="w-3 h-3 text-[#34D399]" />
                </div>
                <div className="flex items-center justify-between">
                  <span>W 5.7 km/h</span>
                  <Wind className="w-3 h-3 text-[#34D399]" />
                </div>

                <div className="flex items-center justify-between">
                  <span>8:39:55 AM</span>
                  <Sunrise className="w-3 h-3 text-amber-400" />
                </div>
                <div className="flex items-center justify-between">
                  <span>5:00:58 PM</span>
                  <Sunset className="w-3 h-3 text-orange-400" />
                </div>

                <div className="flex items-center justify-between">
                  <span>1 UV index</span>
                  <Sun className="w-3 h-3 text-amber-400" />
                </div>
                <div className="flex items-center justify-between">
                  <span>1 / 1 UV index</span>
                  <Sun className="w-3 h-3 text-amber-400" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* COLUMN 3: Hourly Weather + Animated Weather + Meteoalarm                  */}
        {/* ========================================================================= */}
        <div className="space-y-4">
          {/* Card 3A: Hourly Weather Card by decompil3d */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Hourly Weather Card</span>
              <span className="text-[10px] text-[#98B5A5]">by decompil3d</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-3">
              <div className="text-sm font-semibold text-white">Hourly Weather</div>

              {/* Segmented Color Condition Bar */}
              <div className="grid grid-cols-7 rounded-md overflow-hidden h-7 border border-white/10">
                <div className="bg-[#A7C7E7] flex items-center justify-center text-slate-800">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#7BA3CD] flex items-center justify-center text-white">
                  <CloudRain className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#6B8EAE] flex items-center justify-center text-white">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#5B7894] flex items-center justify-center text-white">
                  <CloudRain className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#786D65] flex items-center justify-center text-white">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#506880] flex items-center justify-center text-white">
                  <CloudRain className="w-3.5 h-3.5" />
                </div>
                <div className="bg-[#405468] flex items-center justify-center text-white">
                  <Cloud className="w-3.5 h-3.5" />
                </div>
              </div>

              {/* Hourly Columns */}
              <div className="grid grid-cols-7 text-center text-[10px] text-[#98B5A5] pt-1">
                <div>
                  <div>12:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">4.3°</div>
                </div>
                <div>
                  <div>14:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">5.3°</div>
                </div>
                <div>
                  <div>16:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">4.3°</div>
                  <div className="text-[9px] text-[#34D399] mt-2">0.9 mm</div>
                </div>
                <div>
                  <div>18:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">2.8°</div>
                  <div className="text-[9px] text-[#34D399] mt-2">0.7 mm</div>
                </div>
                <div>
                  <div>20:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">3.6°</div>
                </div>
                <div>
                  <div>22:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">3.1°</div>
                  <div className="text-[9px] text-[#34D399] mt-2">1.7 mm</div>
                </div>
                <div>
                  <div>0:00</div>
                  <div className="font-semibold text-white text-xs mt-0.5">2.6°</div>
                  <div className="text-[9px] text-[#34D399] mt-2">1.8 mm</div>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3B: Animated Weather Card by bramkragten */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Animated Weather Card</span>
              <span className="text-[10px] text-[#98B5A5]">by bramkragten</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-3.5">
              <div className="flex items-center justify-between">
                <Sun className="w-9 h-9 text-amber-400" />
                <div className="text-4xl font-bold text-white tracking-tight">1.6 °C</div>
              </div>

              <div className="grid grid-cols-2 text-[11px] text-[#98B5A5] pt-1">
                <div className="space-y-1">
                  <div>80 %</div>
                  <div>999.7 hPa</div>
                  <div>8:39:55 AM</div>
                </div>
                <div className="text-right space-y-1">
                  <div>S 7.2 km/h</div>
                  <div>km</div>
                  <div>5:00:58 PM</div>
                </div>
              </div>

              {/* 5-Day Columns with Weather Icons */}
              <div className="grid grid-cols-5 gap-1 pt-3 border-t border-white/10 text-center">
                {dailyForecast.map((d, i) => (
                  <div key={i} className="space-y-1">
                    <div className="text-[10px] text-white/70 font-semibold uppercase">{d.day}</div>
                    <div className="flex justify-center my-0.5">
                      {i % 2 === 0 ? (
                        <Sun className="w-4 h-4 text-amber-400" />
                      ) : (
                        <CloudRain className="w-4 h-4 text-blue-400" />
                      )}
                    </div>
                    <div className="text-xs font-semibold text-white">{d.high}°C</div>
                    <div className="text-[10px] text-[#98B5A5]">{d.low}°C</div>
                    <div className="text-[9px] text-[#34D399]">{d.rain} mm</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Card 3C: Meteoalarm Card by MrBartusek */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Meteoalarm Card</span>
              <span className="text-[10px] text-[#98B5A5]">by MrBartusek</span>
            </div>

            <div className="space-y-2">
              {/* No warnings card */}
              <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[18px] p-4 border border-white/10 shadow flex items-center justify-between">
                <Shield className="w-6 h-6 text-white/80" />
                <span className="text-sm font-semibold text-white">No warnings</span>
              </div>

              {/* Moderate snow-ice warning (Orange Card) */}
              <div className="bg-[#FF9800] rounded-[18px] p-4 text-white flex items-center gap-3 shadow-lg shadow-orange-500/25">
                <CloudSnow className="w-8 h-8 fill-white text-white flex-shrink-0" />
                <div className="text-sm font-bold tracking-tight">
                  {activeWarning ? activeWarning.title : "Moderate snow-ice warning"}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* COLUMN 4: Platinum Weather Card + Sun Card                                */}
        {/* ========================================================================= */}
        <div className="space-y-4">
          {/* Card 4A: Platinum Weather Card by Makin-Things */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Platinum Weather Card</span>
              <span className="text-[10px] text-[#98B5A5]">by Makin-Things</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-3 text-white">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs font-semibold text-white">Home</div>
                  <div className="relative mt-1">
                    <Sun className="w-9 h-9 text-amber-400" />
                    <Cloud className="w-7 h-7 text-blue-200 fill-blue-300 absolute -bottom-1 -right-1" />
                  </div>
                </div>
                <div className="text-3xl font-bold text-white tracking-tight">-0.4 °C</div>
              </div>

              <div className="text-center text-xs text-white/90 font-medium pb-1">
                Partly cloudy
              </div>

              {/* Detailed Metrics Table */}
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-[#98B5A5] pt-2 border-t border-white/5">
                <div className="space-y-1">
                  <div>Forecast Max 1 °C</div>
                  <div>Forecast Min 1 °C</div>
                  <div>W 6km/h (Gust 27km/h)</div>
                  <div>948hPa</div>
                  <div>17:00</div>
                </div>

                <div className="space-y-1 text-right">
                  <div>0% 0mm</div>
                  <div>98%</div>
                  <div>UV 1</div>
                  <div>JALINE</div>
                  <div>Thu 08:39</div>
                </div>
              </div>

              {/* 5-Day Columns */}
              <div className="grid grid-cols-5 gap-1 pt-3 border-t border-white/10 text-center">
                {dailyForecast.map((d, i) => (
                  <div key={i} className="space-y-1">
                    <div className="text-[10px] text-white/70 font-semibold uppercase">{d.day}</div>
                    <div className="flex justify-center my-0.5">
                      <Cloud className="w-4 h-4 text-blue-300" />
                    </div>
                    <div className="text-[10px] text-[#98B5A5]">
                      {i === 0 ? "-1/5°C" : i === 1 ? "-1/4°C" : i === 2 ? "-3/3°C" : i === 3 ? "-4/0°C" : "-6/0°C"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Card 4B: Sun Card by AitorDB */}
          <div>
            <div className="mb-1.5 px-1 flex items-baseline justify-between">
              <span className="font-semibold text-xs text-white/90">Sun Card</span>
              <span className="text-[10px] text-[#98B5A5]">by AitorDB</span>
            </div>

            <div className="bg-[#192A21]/90 backdrop-blur-md rounded-[20px] p-4 border border-white/10 shadow-lg space-y-4 text-white">
              <div className="flex items-center justify-between text-xs">
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Sunrise</div>
                  <div className="text-sm font-bold text-white">08:39</div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-[#98B5A5]">Sunset</div>
                  <div className="text-sm font-bold text-white">17:00</div>
                </div>
              </div>

              {/* Solar Arc Curve Graphic matching screenshot */}
              <div className="relative h-20 w-full flex items-center justify-center">
                <svg viewBox="0 0 240 80" className="w-full h-full overflow-visible">
                  {/* Sky dawn wedge */}
                  <polygon points="0,55 120,55 80,30" className="fill-[#3b5998]/40" />
                  <polygon points="120,55 180,55 150,30" className="fill-[#5c6bc0]/50" />

                  {/* Horizon line */}
                  <line x1="0" y1="55" x2="240" y2="55" stroke="#98B5A5" strokeWidth="1.5" strokeOpacity="0.4" />

                  {/* Sun trajectory curve */}
                  <path
                    d="M 20,55 Q 120,-10 220,55"
                    fill="none"
                    stroke="#34D399"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                  />

                  {/* Sun marker positioned on arc */}
                  <circle cx="155" cy="28" r="6" className="fill-amber-400 filter drop-shadow(0 0 6px #F59E0B)" />
                </svg>
              </div>

              {/* Dawn, Solar noon, Dusk */}
              <div className="grid grid-cols-3 text-center text-xs pt-1 border-t border-white/5">
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Dawn</div>
                  <div className="font-semibold text-white mt-0.5">08:00</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Solar noon</div>
                  <div className="font-semibold text-white mt-0.5">12:50</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Dusk</div>
                  <div className="font-semibold text-white mt-0.5">17:40</div>
                </div>
              </div>

              {/* Azimuth, Elevation */}
              <div className="grid grid-cols-2 text-center text-xs pt-1 border-t border-white/5">
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Azimuth</div>
                  <div className="font-semibold text-white mt-0.5">147.7</div>
                </div>
                <div>
                  <div className="text-[10px] text-[#98B5A5]">Elevation</div>
                  <div className="font-semibold text-white mt-0.5">11.36</div>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export default function LiveWeatherPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-96 text-[#98B5A5] font-mono text-sm">
          LOADING HOME ASSISTANT WEATHER DASHBOARD...
        </div>
      }
    >
      <HomeAssistantWeatherDashboard />
    </Suspense>
  );
}
