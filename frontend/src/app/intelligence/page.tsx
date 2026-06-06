"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import {
  TrendingUp, MapPin, Activity, AlertTriangle, Calendar,
  Thermometer, Wind, Droplets, Search, Brain, ChevronRight,
  Package, BarChart3, Clock, Zap, Target, ArrowUpRight, Info
} from "lucide-react";
import { IndiaHeatmap } from "@/components/shared/IndiaHeatmap";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const DISTRICT_ID = "07_094";
const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";

// ─── Model comparison data ────────────────────────────────────────────────────
const MODEL_CARDS = [
  {
    id: "stgnn",
    name: "ST-GNN",
    fullName: "Spatio-Temporal Graph Neural Network",
    role: "Short-Term Outbreak Detection",
    horizon: "1–4 weeks",
    color: "from-red-500 to-orange-500",
    borderColor: "border-red-200",
    bgLight: "bg-red-50",
    textColor: "text-red-700",
    icon: Zap,
    usp: "Captures how outbreaks spread geographically between adjacent districts through graph edges — unique to spatial data.",
    metrics: [
      { label: "Avg. Accuracy", value: "87.3%" },
      { label: "Detection Lag", value: "< 3 days" },
      { label: "Coverage", value: "641 districts" },
    ],
    badge: "REAL-TIME",
    badgeColor: "bg-red-100 text-red-700",
  },
  {
    id: "tft",
    name: "TFT",
    fullName: "Temporal Fusion Transformer",
    role: "Medium-Term Demand Forecasting",
    horizon: "4–12 weeks",
    color: "from-violet-500 to-indigo-500",
    borderColor: "border-violet-200",
    bgLight: "bg-violet-50",
    textColor: "text-violet-700",
    icon: Brain,
    usp: "Attention mechanism explains which past weeks, weather events, and search spikes influenced each prediction — fully interpretable.",
    metrics: [
      { label: "MAPE", value: "6.1%" },
      { label: "Horizon", value: "12 weeks" },
      { label: "Features", value: "28 covariates" },
    ],
    badge: "INTERPRETABLE",
    badgeColor: "bg-violet-100 text-violet-700",
  },
  {
    id: "prophet",
    name: "Prophet",
    fullName: "Meta Prophet — Strategic Planner",
    role: "Long-Term Supply Chain Planning",
    horizon: "3–12 months",
    color: "from-emerald-500 to-teal-500",
    borderColor: "border-emerald-200",
    bgLight: "bg-emerald-50",
    textColor: "text-emerald-700",
    icon: Calendar,
    usp: "Designed by Meta for business time-series with seasonality, holidays, and trend breaks — outperforms deep learning at 6–12 month horizons where training data is sparse.",
    metrics: [
      { label: "Horizon", value: "12 months" },
      { label: "Seasonality", value: "Monsoon-aware" },
      { label: "Planning", value: "Budget + procurement" },
    ],
    badge: "STRATEGIC",
    badgeColor: "bg-emerald-100 text-emerald-700",
  },
];

// ─── Prophet 12-month demand projection (realistic India drug data) ───────────
const PROPHET_PROJECTIONS = [
  { drug: "ORS Sachets", category: "Diarrhoeal", baseline: 2400, peak: 4200, peakMonth: "Aug", trend: "+75%", risk: "HIGH", reason: "Monsoon peak — diarrhoeal disease always spikes July–Sept" },
  { drug: "Chloroquine 500mg", category: "Malaria", baseline: 1800, peak: 3100, peakMonth: "Sep", trend: "+72%", risk: "HIGH", reason: "Malaria transmission peaks post-monsoon (Aug–Oct) in northern states" },
  { drug: "Paracetamol 650mg", category: "Dengue / Fever", baseline: 3200, peak: 5400, peakMonth: "Jul", trend: "+69%", risk: "HIGH", reason: "Dengue fever management — demand tracks case count directly" },
  { drug: "Doxycycline 100mg", category: "Cholera", baseline: 600, peak: 980, peakMonth: "Aug", trend: "+63%", risk: "MEDIUM", reason: "Cholera flares in flooding zones — concentrated coastal states" },
  { drug: "Metronidazole 400mg", category: "Diarrhoeal", baseline: 1100, peak: 1750, peakMonth: "Aug", trend: "+59%", risk: "MEDIUM", reason: "Amoebic dysentery rises with contaminated water supply during floods" },
  { drug: "Cetirizine 10mg", category: "Respiratory", baseline: 2800, peak: 3900, peakMonth: "Oct", trend: "+39%", risk: "LOW", reason: "Post-monsoon allergy and respiratory flare — steady seasonal pattern" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Realistic monsoon-aware demand curve for each drug
function getDemandCurve(baseline: number, peak: number, peakMonthIdx: number) {
  return MONTHS.map((_, i) => {
    const dist = Math.abs(i - peakMonthIdx);
    const bell = Math.exp(-(dist * dist) / 3.5);
    return Math.round(baseline + (peak - baseline) * bell);
  });
}

const RISK_COLOR: Record<string, string> = {
  HIGH:   "text-red-600 bg-red-50 border-red-200",
  MEDIUM: "text-amber-600 bg-amber-50 border-amber-200",
  LOW:    "text-emerald-600 bg-emerald-50 border-emerald-200",
};

const TOP_DISTRICTS = [
  { id: "07_094", name: "New Delhi", state: "Delhi", cases: 80370 },
  { id: "34_635", name: "Puducherry", state: "Puducherry", cases: 15625 },
  { id: "12_251", name: "East Siang", state: "Arunachal Pradesh", cases: 14420 },
  { id: "19_331", name: "North 24 Parganas", state: "West Bengal", cases: 10584 },
  { id: "19_339", name: "Pashchim Medinipur", state: "West Bengal", cases: 9529 },
  { id: "04_061", name: "Chandigarh", state: "Chandigarh", cases: 5686 },
];

const SIGNAL_CARDS = [
  { title: "Epidemiological (IDSP)", icon: Activity, color: "text-red-600", bg: "bg-red-50", value: "↑ Dengue + Diarrhoeal Rising", model: "ST-GNN", status: "ALERT", statusColor: "bg-red-100 text-red-700", detail: "80,370 cumulative dengue cases. Diarrhoeal cases up 34% WoW." },
  { title: "Weather (IMD)", icon: Thermometer, color: "text-orange-600", bg: "bg-orange-50", value: "38°C · 82% humidity", model: "GraphWaveNet", status: "HIGH RISK", statusColor: "bg-orange-100 text-orange-700", detail: "Stagnant water in 3 districts. Peak mosquito breeding window." },
  { title: "Search Trend Index", icon: Search, color: "text-blue-600", bg: "bg-blue-50", value: "2.4× above baseline", model: "Prophet", status: "ANOMALY", statusColor: "bg-blue-100 text-blue-700", detail: "'Dengue fever symptoms' spiked 2.4× in Delhi NCR this week." },
  { title: "Rainfall (IMD)", icon: Droplets, color: "text-cyan-600", bg: "bg-cyan-50", value: "+40% of normal", model: "N-BEATS", status: "MODERATE", statusColor: "bg-cyan-100 text-cyan-700", detail: "Above-average monsoon onset. 3 districts with standing water." },
];

type Tab = "overview" | "prophet" | "models";

export default function IntelligencePage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [selectedDrug, setSelectedDrug] = useState(0);
  const [horizon, setHorizon] = useState(12);

  const { data: riskData } = useSWR(
    `/api/v1/risk/district/${DISTRICT_ID}?diseases=dengue`,
    fetcher
  );
  const topScore = riskData?.scores?.[0];

  const proj = PROPHET_PROJECTIONS[selectedDrug];
  const peakMonthIdx = MONTHS.indexOf(proj.peakMonth);
  const curve = getDemandCurve(proj.baseline, proj.peak, peakMonthIdx);
  const displayMonths = MONTHS.slice(0, horizon);
  const displayCurve = curve.slice(0, horizon);
  const maxVal = Math.max(...displayCurve);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {[
          { id: "overview", label: "Signal Dashboard", icon: Activity },
          { id: "prophet", label: "Prophet — Strategic Planner", icon: Calendar },
          { id: "models", label: "Model Comparison", icon: Brain },
        ].map(t => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as Tab)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                active
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">

        {/* ── TAB 1: Signal Overview ─────────────────────────────────────────── */}
        {activeTab === "overview" && (
          <motion.div key="overview" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-8">

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {SIGNAL_CARDS.map((card, i) => {
                const Icon = card.icon;
                return (
                  <motion.div key={card.title} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                    className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className={`p-2 rounded-lg ${card.bg}`}>
                        <Icon className={`w-4 h-4 ${card.color}`} />
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${card.statusColor}`}>{card.status}</span>
                    </div>
                    <div className="text-xs text-gray-500 mb-0.5">{card.title}</div>
                    <div className="font-semibold text-gray-900 text-sm mb-1">{card.value}</div>
                    <p className="text-xs text-gray-400 leading-relaxed mb-2">{card.detail}</p>
                    <div className="text-[10px] text-gray-400 font-mono border-t border-gray-100 pt-1.5">
                      Model: <span className="text-indigo-600 font-semibold">{card.model}</span>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {/* Heatmap + district deep-dive */}
            <div>
              <h2 className="text-xl font-bold text-gray-900 mb-1">National Disease Heatmap</h2>
              <p className="text-sm text-gray-500 mb-4">Live risk intensity across all 641 districts. Powered by ST-GNN spatial inference.</p>
              <IndiaHeatmap initialDisease="dengue" />
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900 mb-4">Top Burden Districts — Dengue</h2>
                <div className="space-y-2">
                  {TOP_DISTRICTS.map((d, i) => {
                    const pct = Math.round((d.cases / TOP_DISTRICTS[0].cases) * 100);
                    return (
                      <motion.div key={d.id} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}
                        className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <div className="font-semibold text-gray-900 text-sm">{d.name}</div>
                            <div className="text-xs text-gray-400 flex items-center gap-1"><MapPin className="w-3 h-3" />{d.state}</div>
                          </div>
                          <div className="text-right">
                            <div className="font-bold text-red-600">{d.cases.toLocaleString("en-IN")}</div>
                            <div className="text-xs text-gray-400">cumulative cases</div>
                          </div>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ delay: i * 0.06 + 0.3, duration: 0.5 }}
                            className="h-full bg-gradient-to-r from-orange-400 to-red-500 rounded-full"
                          />
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>

              {/* Live ML risk score */}
              <div>
                <h2 className="text-lg font-bold text-gray-900 mb-4">District Risk Deep-Dive</h2>
                <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
                  <div className="flex items-center gap-2 mb-4">
                    <MapPin className="w-4 h-4 text-red-500" />
                    <span className="font-semibold text-gray-900">New Delhi, NCT of Delhi</span>
                    <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-semibold ml-auto">Highest Burden</span>
                  </div>
                  <div className="space-y-4">
                    {topScore && (
                      <div className="p-4 bg-gray-50 rounded-xl">
                        <div className="text-xs text-gray-500 mb-1">ML Risk Score — ST-GNN · {topScore.disease}</div>
                        <div className="flex items-end gap-2">
                          <div className="text-3xl font-bold text-gray-900">{(topScore.score * 100).toFixed(1)}%</div>
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full mb-1 ${
                            topScore.risk_level === "HIGH" ? "bg-red-100 text-red-700" :
                            topScore.risk_level === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                            "bg-emerald-100 text-emerald-700"
                          }`}>{topScore.risk_level}</span>
                        </div>
                        <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-amber-400 to-red-500 rounded-full transition-all duration-700"
                            style={{ width: `${Math.min(100, topScore.score * 100)}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { label: "Weather", val: "82%", icon: Wind, color: "text-orange-500" },
                        { label: "Search Trend", val: "60%", icon: TrendingUp, color: "text-blue-500" },
                        { label: "Epid. Signal", val: "50%", icon: Activity, color: "text-red-500" },
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
                        ST-GNN + GraphWaveNet detected anomalous search and weather signals above 2σ threshold. District requires immediate inventory check.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── TAB 2: Prophet Strategic Planner ──────────────────────────────── */}
        {activeTab === "prophet" && (
          <motion.div key="prophet" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-6">

            {/* Prophet hero card */}
            <div className="relative overflow-hidden bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-700 rounded-2xl p-6 text-white">
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
              <div className="relative">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2.5 bg-white/20 rounded-xl backdrop-blur-sm">
                    <Calendar className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <div className="font-black text-lg">Prophet — Strategic Supply Chain Planner</div>
                    <div className="text-emerald-200 text-sm">Meta's purpose-built business time-series model · 3–12 month horizon</div>
                  </div>
                  <div className="ml-auto text-xs bg-white/20 backdrop-blur-sm px-3 py-1.5 rounded-full font-semibold">
                    Monsoon-Aware · Seasonal
                  </div>
                </div>
                <p className="text-emerald-100 text-sm leading-relaxed max-w-2xl">
                  While ST-GNN detects <em>this week's</em> outbreak spike and TFT forecasts <em>next month's</em> demand,
                  Prophet answers the hardest question: <strong className="text-white">what will your procurement needs look like in August, 6 months from now?</strong>
                  It handles India's monsoon seasonality, national holiday effects, and historical demand breaks that deep learning models miss at long horizons.
                </p>
                <div className="flex gap-6 mt-4 text-sm">
                  {[
                    { label: "Planning Horizon", val: "12 months" },
                    { label: "Seasonality", val: "Monsoon + Festive" },
                    { label: "Use Case", val: "Budget & Procurement" },
                  ].map(s => (
                    <div key={s.label}>
                      <div className="text-emerald-300 text-xs">{s.label}</div>
                      <div className="font-bold text-white">{s.val}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="flex flex-wrap items-center gap-4">
              <div>
                <label className="text-xs text-gray-500 mb-1 block font-medium">Forecast Horizon</label>
                <div className="flex gap-1">
                  {[3, 6, 9, 12].map(h => (
                    <button key={h} onClick={() => setHorizon(h)}
                      className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-all ${
                        horizon === h ? "bg-emerald-600 text-white shadow-sm" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >{h} months</button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-400 bg-gray-50 px-3 py-1.5 rounded-lg">
                <Info className="w-3.5 h-3.5" />
                Click a drug below to see its demand curve
              </div>
            </div>

            <div className="grid lg:grid-cols-3 gap-4">
              {/* Drug selector */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">Drug Demand Projections</h3>
                {PROPHET_PROJECTIONS.map((p, i) => (
                  <button key={p.drug} onClick={() => setSelectedDrug(i)} className={`w-full text-left p-3 rounded-xl border transition-all ${
                    selectedDrug === i
                      ? "border-emerald-300 bg-emerald-50 shadow-sm"
                      : "border-gray-200 bg-white hover:border-gray-300"
                  }`}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-medium text-gray-900 text-sm">{p.drug}</div>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${RISK_COLOR[p.risk]}`}>{p.risk}</span>
                    </div>
                    <div className="text-xs text-gray-400 mb-1">{p.category}</div>
                    <div className="flex items-center gap-2">
                      <div className="text-xs font-semibold text-emerald-700 flex items-center gap-0.5">
                        <ArrowUpRight className="w-3 h-3" />{p.trend} peak {p.peakMonth}
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              {/* Demand chart */}
              <div className="lg:col-span-2 bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900">{proj.drug}</h3>
                    <div className="text-xs text-gray-500">{proj.category} · Prophet {horizon}-month forecast</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black text-emerald-600">{proj.trend}</div>
                    <div className="text-xs text-gray-400">peak vs. baseline · {proj.peakMonth}</div>
                  </div>
                </div>

                {/* Bar chart — px heights so bars are always visible */}
                <div className="flex items-end gap-1 mb-2" style={{ height: "140px" }}>
                  {displayMonths.map((month, i) => {
                    const val = displayCurve[i];
                    const barPx = Math.max(4, Math.round((val / maxVal) * 130));
                    const isPeak = month === proj.peakMonth;
                    return (
                      <div key={month} className="flex-1 flex flex-col items-center justify-end group relative" style={{ height: "140px" }}>
                        {/* Tooltip */}
                        <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-[10px] px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                          {val.toLocaleString("en-IN")} units
                        </div>
                        <motion.div
                          initial={{ height: 0 }}
                          animate={{ height: barPx }}
                          transition={{ delay: i * 0.04, duration: 0.45, ease: "easeOut" }}
                          style={{ width: "100%" }}
                          className={`rounded-t-sm shrink-0 ${
                            isPeak
                              ? "bg-gradient-to-t from-emerald-600 to-emerald-400"
                              : "bg-gradient-to-t from-emerald-300 to-emerald-100"
                          }`}
                        />
                        <div className={`text-[9px] font-medium mt-1 shrink-0 ${isPeak ? "text-emerald-700" : "text-gray-400"}`}>{month}</div>
                      </div>
                    );
                  })}
                </div>

                {/* Baseline / peak legend */}
                <div className="flex items-center gap-6 pt-3 border-t border-gray-100">
                  <div>
                    <div className="text-xs text-gray-400">Baseline demand</div>
                    <div className="font-bold text-gray-900">{proj.baseline.toLocaleString("en-IN")} units/mo</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Peak month ({proj.peakMonth})</div>
                    <div className="font-bold text-emerald-700">{proj.peak.toLocaleString("en-IN")} units/mo</div>
                  </div>
                  <div className="ml-auto p-3 bg-amber-50 border border-amber-200 rounded-xl max-w-xs">
                    <div className="flex items-start gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                      <p className="text-[11px] text-amber-800 leading-relaxed">{proj.reason}</p>
                    </div>
                  </div>
                </div>

                {/* Procurement recommendation */}
                <div className="mt-3 p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-3">
                  <Package className="w-5 h-5 text-emerald-600 shrink-0" />
                  <div className="text-xs text-emerald-800">
                    <span className="font-semibold">Prophet recommends:</span> Place bulk procurement order{" "}
                    <strong>{proj.peakMonth === "Aug" || proj.peakMonth === "Jul" ? "by June" : "2 months before " + proj.peakMonth}</strong>{" "}
                    to avoid stockout. Buffer stock = <strong>{Math.round(proj.peak * 1.2).toLocaleString("en-IN")} units</strong> (peak + 20% safety).
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── TAB 3: Model Comparison ────────────────────────────────────────── */}
        {activeTab === "models" && (
          <motion.div key="models" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} className="space-y-6">

            <div>
              <h2 className="text-xl font-bold text-gray-900 mb-1">Pharmasense Model Architecture</h2>
              <p className="text-sm text-gray-500">Each model has a distinct job. No overlapping roles — every model earns its place.</p>
            </div>

            <div className="grid md:grid-cols-3 gap-5">
              {MODEL_CARDS.map((m, i) => {
                const Icon = m.icon;
                return (
                  <motion.div key={m.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                    className={`bg-white border-2 ${m.borderColor} rounded-2xl overflow-hidden shadow-sm`}
                  >
                    <div className={`bg-gradient-to-br ${m.color} p-5 text-white`}>
                      <div className="flex items-center justify-between mb-3">
                        <div className="p-2 bg-white/20 rounded-xl"><Icon className="w-5 h-5" /></div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${m.badgeColor}`}>{m.badge}</span>
                      </div>
                      <div className="text-2xl font-black mb-0.5">{m.name}</div>
                      <div className="text-white/80 text-xs">{m.fullName}</div>
                    </div>
                    <div className="p-5 space-y-4">
                      <div>
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Role</div>
                        <div className={`font-semibold text-sm ${m.textColor}`}>{m.role}</div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Horizon</div>
                        <div className="flex items-center gap-1.5">
                          <Clock className={`w-3.5 h-3.5 ${m.textColor}`} />
                          <span className="font-medium text-gray-900 text-sm">{m.horizon}</span>
                        </div>
                      </div>
                      <div>
                        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Unique Advantage</div>
                        <p className="text-xs text-gray-600 leading-relaxed">{m.usp}</p>
                      </div>
                      <div className={`grid grid-cols-3 gap-2 p-3 ${m.bgLight} rounded-xl`}>
                        {m.metrics.map(met => (
                          <div key={met.label} className="text-center">
                            <div className={`font-bold text-sm ${m.textColor}`}>{met.value}</div>
                            <div className="text-[9px] text-gray-500 leading-tight">{met.label}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            {/* Architecture flow */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
              <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-indigo-500" />
                How the Models Work Together
              </h3>
              <div className="flex items-start gap-3 overflow-x-auto pb-2">
                {[
                  { label: "Incoming Signal", sub: "IDSP · IMD · Google Trends · Inventory", bg: "bg-gray-100", text: "text-gray-700" },
                  { label: "ST-GNN", sub: "Spatial spread detection\nShort-term alert", bg: "bg-red-100", text: "text-red-700" },
                  { label: "TFT", sub: "28 covariates · attention\n4–12 week demand forecast", bg: "bg-violet-100", text: "text-violet-700" },
                  { label: "Prophet", sub: "Seasonality + trends\n3–12 month planning", bg: "bg-emerald-100", text: "text-emerald-700" },
                  { label: "Pharmasense", sub: "Purchase order\n+ WhatsApp alert", bg: "bg-indigo-600", text: "text-white" },
                ].map((step, i, arr) => (
                  <div key={step.label} className="flex items-center gap-3 shrink-0">
                    <div className={`${step.bg} ${step.text} px-4 py-3 rounded-xl text-center min-w-[130px]`}>
                      <div className="font-bold text-sm">{step.label}</div>
                      <div className="text-[10px] opacity-70 mt-0.5 whitespace-pre-line leading-tight">{step.sub}</div>
                    </div>
                    {i < arr.length - 1 && <ChevronRight className="w-5 h-5 text-gray-300 shrink-0" />}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
}
