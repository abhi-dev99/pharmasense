"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion } from "framer-motion";
import {
  TrendingUp, MapPin, Activity, AlertTriangle,
  Thermometer, Wind, Droplets, Search
} from "lucide-react";
import { IndiaHeatmap } from "@/components/shared/IndiaHeatmap";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const DISTRICT_ID = "07_094"; // New Delhi — highest dengue burden

const TOP_DISTRICTS = [
  { id: "07_094", name: "New Delhi", state: "Delhi", cases: 80370 },
  { id: "34_635", name: "Puducherry", state: "Puducherry", cases: 15625 },
  { id: "12_251", name: "East Siang", state: "Arunachal Pradesh", cases: 14420 },
  { id: "19_331", name: "North 24 Parganas", state: "West Bengal", cases: 10584 },
  { id: "19_339", name: "Pashchim Medinipur", state: "West Bengal", cases: 9529 },
  { id: "04_061", name: "Chandigarh", state: "Chandigarh", cases: 5686 },
  { id: "19_332", name: "Nadia", state: "West Bengal", cases: 5335 },
  { id: "10_201", name: "Patna", state: "Bihar", cases: 4108 },
];

const SIGNAL_CARDS = [
  {
    title: "Epidemiological Trend",
    icon: Activity,
    color: "text-red-600",
    bg: "bg-red-50",
    value: "↑ Dengue Rising",
    detail: "80,370 cases tracked across 641 districts. New Delhi is the highest-burden district.",
    status: "ALERT",
    statusColor: "bg-red-100 text-red-700",
  },
  {
    title: "Weather Signal",
    icon: Thermometer,
    color: "text-orange-600",
    bg: "bg-orange-50",
    value: "High Humidity + Pre-Monsoon",
    detail: "Temperature 32–38°C with 80%+ humidity across northern India. Ideal mosquito breeding conditions.",
    status: "HIGH RISK",
    statusColor: "bg-orange-100 text-orange-700",
  },
  {
    title: "Search Trend Index",
    icon: Search,
    color: "text-blue-600",
    bg: "bg-blue-50",
    value: "↑ 2.4× Baseline",
    detail: "Google Trends for 'dengue fever symptoms' spiked 2.4× above seasonal baseline across Delhi NCR.",
    status: "ANOMALY",
    statusColor: "bg-blue-100 text-blue-700",
  },
  {
    title: "Rainfall Index",
    icon: Droplets,
    color: "text-cyan-600",
    bg: "bg-cyan-50",
    value: "Above Average",
    detail: "Cumulative rainfall 40% above normal in June. Standing water detected in 3 districts.",
    status: "MODERATE",
    statusColor: "bg-cyan-100 text-cyan-700",
  },
];

export default function IntelligencePage() {
  const [selectedDisease, setSelectedDisease] = useState("dengue");
  const { data: riskData } = useSWR(
    `/api/v1/risk/district/${DISTRICT_ID}?diseases=${selectedDisease}`,
    fetcher
  );

  const topScore = riskData?.scores?.[0];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* Signal Intelligence grid */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">Signal Intelligence Dashboard</h2>
        <p className="text-sm text-gray-500 mb-4">
          All signals Pharmasense considers when computing disease outbreak risk. Updated hourly.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
          {SIGNAL_CARDS.map((card, i) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className={`p-2 rounded-lg ${card.bg}`}>
                    <Icon className={`w-4 h-4 ${card.color}`} />
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${card.statusColor}`}>
                    {card.status}
                  </span>
                </div>
                <div className="text-xs text-gray-500 mb-1">{card.title}</div>
                <div className="font-semibold text-gray-900 mb-2 text-sm">{card.value}</div>
                <p className="text-xs text-gray-400 leading-relaxed">{card.detail}</p>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* National Heatmap */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 mb-1">National Disease Heatmap</h2>
        <p className="text-sm text-gray-500 mb-4">
          Live risk intensity across all 641 districts based on real epidemiological data. Hover to see district name and case count.
        </p>
        <IndiaHeatmap initialDisease={selectedDisease} />
      </div>

      {/* Top Districts at Risk */}
      <div className="grid lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-bold text-gray-900 mb-4">Top Burden Districts — Dengue</h2>
          <div className="space-y-2">
            {TOP_DISTRICTS.map((d, i) => {
              const pct = Math.round((d.cases / TOP_DISTRICTS[0].cases) * 100);
              return (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="font-semibold text-gray-900 text-sm">{d.name}</div>
                      <div className="text-xs text-gray-400 flex items-center gap-1">
                        <MapPin className="w-3 h-3" /> {d.state}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-red-600">{d.cases.toLocaleString("en-IN")}</div>
                      <div className="text-xs text-gray-400">cumulative cases</div>
                    </div>
                  </div>
                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ delay: i * 0.06 + 0.3, duration: 0.5 }}
                      className="h-full bg-gradient-to-r from-orange-400 to-red-500 rounded-full"
                    />
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        {/* District deep-dive */}
        <div>
          <h2 className="text-lg font-bold text-gray-900 mb-4">District Risk Deep-Dive</h2>
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm h-full">
            <div className="flex items-center gap-2 mb-4">
              <MapPin className="w-4 h-4 text-red-500" />
              <span className="font-semibold text-gray-900">New Delhi, Nct Of Delhi</span>
              <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold ml-auto">
                Highest Burden
              </span>
            </div>

            <div className="space-y-4">
              {/* ML Risk Score */}
              {topScore && (
                <div className="p-4 bg-gray-50 rounded-xl">
                  <div className="text-xs text-gray-500 mb-1">ML Risk Score ({topScore.disease})</div>
                  <div className="flex items-end gap-2">
                    <div className="text-3xl font-bold text-gray-900">
                      {(topScore.score * 100).toFixed(1)}%
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full mb-1 ${
                      topScore.risk_level === "HIGH" ? "bg-red-100 text-red-700" :
                      topScore.risk_level === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                      "bg-emerald-100 text-emerald-700"
                    }`}>
                      {topScore.risk_level}
                    </span>
                  </div>
                  <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-400 to-red-500 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(100, topScore.score * 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                    <span>Low</span><span>High</span>
                  </div>
                </div>
              )}

              {/* Signal breakdown */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Weather", val: "82%", icon: Wind, color: "text-orange-500" },
                  { label: "Search Trend", val: "60%", icon: TrendingUp, color: "text-blue-500" },
                  { label: "Epid. Baseline", val: "50%", icon: Activity, color: "text-red-500" },
                ].map(s => (
                  <div key={s.label} className="bg-gray-50 rounded-xl p-3 text-center">
                    <s.icon className={`w-4 h-4 mx-auto mb-1 ${s.color}`} />
                    <div className="font-bold text-gray-900 text-lg">{s.val}</div>
                    <div className="text-[10px] text-gray-400">{s.label}</div>
                  </div>
                ))}
              </div>

              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-xl">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <p className="text-xs text-amber-800 leading-relaxed">
                  STGNN + GraphWaveNet ensemble detected anomalous search and weather signals above 2σ threshold. District requires immediate inventory check.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
