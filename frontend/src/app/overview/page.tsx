"use client";

import useSWR from "swr";
import { motion } from "framer-motion";
import {
  Activity, AlertTriangle, PackageOpen, ShieldCheck,
  Thermometer, Search, Droplets, Wind, BarChart3, Waves
} from "lucide-react";
import { RiskPanel } from "@/components/dashboard/RiskPanel";
import { OrderTable } from "@/components/dashboard/OrderTable";
import { AIBrief } from "@/components/dashboard/AIBrief";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";
const DISTRICT_ID = "07_094";

// Risk level → color helpers
function riskColor(level: "ok" | "moderate" | "high" | "critical") {
  if (level === "ok")       return { val: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-700" };
  if (level === "moderate") return { val: "text-amber-600",   bg: "bg-amber-50",   border: "border-amber-200",   badge: "bg-amber-100 text-amber-700" };
  if (level === "high")     return { val: "text-orange-600",  bg: "bg-orange-50",  border: "border-orange-200",  badge: "bg-orange-100 text-orange-700" };
  return                           { val: "text-red-600",     bg: "bg-red-50",     border: "border-red-200",     badge: "bg-red-100 text-red-700" };
}

const SIGNALS = [
  {
    id: "epid",
    label: "Dengue / Arboviral",
    sublabel: "Weekly case counts · ICMR / IDSP",
    model: "ST-GNN",
    icon: Activity,
    iconColor: "text-red-500",
    value: "68,000×",
    valueSuffix: "above baseline",
    detail: "Dengue trending far above seasonal baseline in New Delhi district",
    risk: "critical" as const,
    status: "ALERT",
  },
  {
    id: "diarrhoeal",
    label: "Diarrhoeal Disease",
    sublabel: "Cholera · Acute gastro · IDSP surveillance",
    model: "Prophet",
    icon: Droplets,
    iconColor: "text-teal-500",
    value: "↑ 34%",
    valueSuffix: "WoW rise",
    detail: "Acute diarrhoeal cases up 34% week-on-week — monsoon-linked",
    risk: "high" as const,
    status: "WATCH",
  },
  {
    id: "weather",
    label: "Weather & Climate",
    sublabel: "Temp · Humidity · Rainfall · IMD",
    model: "GraphWaveNet",
    icon: Thermometer,
    iconColor: "text-orange-500",
    value: "38°C / 82%",
    valueSuffix: "humidity",
    detail: "Stagnant water zones identified — peak vector breeding conditions",
    risk: "high" as const,
    status: "RISK",
  },
  {
    id: "search",
    label: "Search Trend Index",
    sublabel: "Google Trends proxy signal",
    model: "Prophet",
    icon: Search,
    iconColor: "text-blue-500",
    value: "2.4×",
    valueSuffix: "vs baseline",
    detail: "'Dengue fever symptoms' spiked 2.4× in Delhi NCR this week",
    risk: "high" as const,
    status: "ANOMALY",
  },
  {
    id: "rainfall",
    label: "Rainfall Index",
    sublabel: "IMD cumulative · district-level",
    model: "N-BEATS",
    icon: Wind,
    iconColor: "text-cyan-500",
    value: "+40%",
    valueSuffix: "of normal",
    detail: "Above-average monsoon onset. 3 districts with standing water.",
    risk: "moderate" as const,
    status: "MODERATE",
  },
  {
    id: "ml",
    label: "ML Ensemble Score",
    sublabel: "Spatial + temporal consensus",
    model: "ST-GNN + TFT",
    icon: BarChart3,
    iconColor: "text-indigo-500",
    value: "66%",
    valueSuffix: "confidence",
    detail: "Ensemble predicts continued dengue + diarrhoeal disease co-rise over 4 weeks",
    risk: "high" as const,
    status: "ACTIVE",
  },
];

export default function OverviewPage() {
  const { data: forecastData } = useSWR(`/api/v1/forecast/hospital/${HOSPITAL_ID}`, fetcher);
  const { data: hospData }     = useSWR(`/api/v1/hospitals/${HOSPITAL_ID}`, fetcher);
  const { data: ordersData }   = useSWR(`/api/v1/orders/hospital/${HOSPITAL_ID}`, fetcher);

  const pendingOrdersCount = forecastData?.orders?.length ?? 0;
  const criticalDrugCount  = forecastData?.orders?.filter((o: any) => o.urgency === "HIGH").length ?? 0;
  const pendingApprovals   = ordersData?.orders?.filter((o: any) => o.status === "DRAFT" || o.status === "PENDING_APPROVAL").length ?? 0;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* Top KPI row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Critical Drug Alerts",    value: criticalDrugCount, sub: `${pendingOrdersCount} total recommendations`, icon: AlertTriangle, color: "text-red-500",     loading: !forecastData },
          { label: "Active Outbreak Signals", value: 4,                 sub: "Dengue · Weather · Search · Rainfall",        icon: Activity,      color: "text-amber-500",   loading: false },
          { label: "Pending PO Approvals",    value: pendingApprovals,  sub: pendingApprovals > 0 ? "Action required" : "All clear", icon: PackageOpen, color: "text-indigo-500", loading: !ordersData },
          { label: "Data Pipelines",          value: "99.9%",           sub: "ICMR · IMD · Google · Supabase synced",        icon: ShieldCheck,   color: "text-emerald-500", loading: false },
        ].map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-600">{card.label}</span>
                <Icon className={`w-4 h-4 ${card.color}`} />
              </div>
              {card.loading ? (
                <div className="h-8 w-16 bg-gray-100 rounded animate-pulse" />
              ) : (
                <div className={`text-3xl font-bold ${card.color}`}>{card.value}</div>
              )}
              <p className="text-xs text-gray-400 mt-1">{card.sub}</p>
            </motion.div>
          );
        })}
      </div>

      {/* Holistic Signal Status — redesigned */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Wind className="w-5 h-5 text-gray-700" />
          <h2 className="text-lg font-bold text-gray-900">Risk Signal Status</h2>
          <span className="ml-auto text-xs text-gray-400">6 signals · Dengue · Diarrhoeal · Weather · Search · Rainfall · ML Ensemble</span>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
          {SIGNALS.map((signal, i) => {
            const Icon = signal.icon;
            const c = riskColor(signal.risk);
            return (
              <motion.div
                key={signal.id}
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.06 }}
                className={`bg-white border rounded-xl p-4 shadow-sm flex flex-col gap-2 ${c.border}`}
              >
                {/* Header row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`p-1.5 rounded-lg ${c.bg}`}>
                      <Icon className={`w-3.5 h-3.5 ${signal.iconColor}`} />
                    </div>
                    <span className="font-semibold text-gray-900 text-sm">{signal.label}</span>
                  </div>
                  {/* Model badge */}
                  <span className="text-[9px] font-bold font-mono px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded border border-gray-200 shrink-0">
                    {signal.model}
                  </span>
                </div>

                {/* Big highlighted value */}
                <div className={`text-2xl font-black tracking-tight leading-none ${c.val}`}>
                  {signal.value}
                  <span className="text-xs font-medium ml-1.5 opacity-70">{signal.valueSuffix}</span>
                </div>

                {/* Status pill + sublabel */}
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${c.badge}`}>
                    {signal.status}
                  </span>
                  <span className="text-[10px] text-gray-400">{signal.sublabel}</span>
                </div>

                {/* Detail text */}
                <p className="text-[11px] text-gray-500 leading-relaxed border-t border-gray-100 pt-2">
                  {signal.detail}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* AI Brief — compact banner */}
      <AIBrief hospitalId={HOSPITAL_ID} />

      {/* Risk panel + full-width order table */}
      <RiskPanel districtId={DISTRICT_ID} diseases="dengue,malaria,acute_diarrhoeal_disease,cholera" />
      <OrderTable hospitalId={HOSPITAL_ID} />
    </div>
  );
}
