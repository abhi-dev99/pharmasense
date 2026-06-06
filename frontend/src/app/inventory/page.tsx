"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, ArrowUpDown, ArrowUp, ArrowDown, Filter,
  Package, AlertTriangle, CheckCircle, Clock
} from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());
const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";

type SortKey = "name" | "dose" | "price" | "stock" | "reorder" | "days_cover" | "status";
type SortDir = "asc" | "desc";
type StatusFilter = "all" | "critical" | "low" | "ok";

/**
 * Status based on stock-to-reorder ratio — realistic and DB-grounded.
 * stock / reorder:
 *   < 1.0  → Critical (below reorder point)
 *   1–2    → Low
 *   > 2    → OK
 * Also compute a "days cover" estimate from a sensible per-unit consumption
 * rate (10 units / 1000 stock ≈ reference), scaled so demo data looks real.
 */
function getStatus(stock: number, reorder: number) {
  const ratio = reorder > 0 ? stock / reorder : 10;

  // Days cover: assume one "cycle" burns through the reorder qty in ~30 days
  // i.e., daily_usage ≈ reorder / 30
  const dailyUsage = Math.max(1, reorder / 30);
  const days = Math.round(stock / dailyUsage);

  if (ratio < 1.0 || days < 7) {
    return { label: "Critical", color: "bg-red-100 text-red-700 border-red-200",     icon: "🔴", days };
  }
  if (ratio < 2.0 || days < 30) {
    return { label: "Low",      color: "bg-amber-100 text-amber-700 border-amber-200", icon: "🟡", days };
  }
  return   { label: "OK",       color: "bg-emerald-100 text-emerald-700 border-emerald-200", icon: "🟢", days };
}

export default function InventoryPage() {
  const { data, isLoading } = useSWR(`/api/v1/hospitals/${HOSPITAL_ID}/inventory`, fetcher);

  const [search,        setSearch]        = useState("");
  const [sortKey,       setSortKey]       = useState<SortKey>("status");
  const [sortDir,       setSortDir]       = useState<SortDir>("asc");
  const [statusFilter,  setStatusFilter]  = useState<StatusFilter>("all");
  const [diseaseFilter, setDiseaseFilter] = useState("all");

  const rows = useMemo(() => {
    const inv: any[] = data?.inventory ?? [];
    return inv.map((row: any) => {
      const drug   = row.drugs ?? {};
      const status = getStatus(row.stock_units, row.reorder_point);
      return {
        id:        drug.id,
        name:      drug.name ?? "Unknown",
        dose:      drug.dose_mg ? `${drug.dose_mg}mg` : "—",
        formulation: drug.formulation_type ?? "—",
        price:     Number(drug.price_inr ?? 0),
        diseases:  drug.icmr_diseases ?? [],
        stock:     row.stock_units,
        reorder:   row.reorder_point,
        days_cover: status.days,
        status,
        updated_at: row.updated_at,
      };
    });
  }, [data]);

  const allDiseases = useMemo(() => {
    const ds = new Set<string>();
    rows.forEach(r => r.diseases.forEach((d: string) => ds.add(d)));
    return Array.from(ds).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    let result = rows;
    if (search) result = result.filter(r =>
      r.name.toLowerCase().includes(search.toLowerCase())
    );
    if (statusFilter !== "all") {
      result = result.filter(r => r.status.label.toLowerCase() === statusFilter);
    }
    if (diseaseFilter !== "all") {
      result = result.filter(r => r.diseases.includes(diseaseFilter));
    }
    result = [...result].sort((a, b) => {
      let av: any = a[sortKey === "status" ? "days_cover" : sortKey];
      let bv: any = b[sortKey === "status" ? "days_cover" : sortKey];
      if (typeof av === "string") av = av.toLowerCase();
      if (typeof bv === "string") bv = bv.toLowerCase();
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return result;
  }, [rows, search, sortKey, sortDir, statusFilter, diseaseFilter]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <ArrowUpDown className="w-3.5 h-3.5 opacity-40" />;
    return sortDir === "asc" ? <ArrowUp className="w-3.5 h-3.5 text-[#111]" /> : <ArrowDown className="w-3.5 h-3.5 text-[#111]" />;
  }

  const stats = useMemo(() => ({
    total:    rows.length,
    critical: rows.filter(r => r.status.label === "Critical").length,
    low:      rows.filter(r => r.status.label === "Low").length,
    ok:       rows.filter(r => r.status.label === "OK").length,
  }), [rows]);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total SKUs",      val: stats.total,    icon: Package,       color: "text-gray-700"    },
          { label: "Critical (<7d)",  val: stats.critical, icon: AlertTriangle, color: "text-red-600"     },
          { label: "Low Stock (<30d)",val: stats.low,      icon: Clock,         color: "text-amber-600"   },
          { label: "Healthy",         val: stats.ok,       icon: CheckCircle,   color: "text-emerald-600" },
        ].map(s => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3 shadow-sm">
            <s.icon className={`w-5 h-5 ${s.color}`} />
            <div>
              <div className={`text-2xl font-bold ${s.color}`}>{isLoading ? "—" : s.val}</div>
              <div className="text-xs text-gray-500 mt-0.5">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search drug name…"
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900/10"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as StatusFilter)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900/10 bg-white"
          >
            <option value="all">All Status</option>
            <option value="critical">🔴 Critical</option>
            <option value="low">🟡 Low</option>
            <option value="ok">🟢 OK</option>
          </select>

          <select
            value={diseaseFilter}
            onChange={e => setDiseaseFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900/10 bg-white"
          >
            <option value="all">All Diseases</option>
            {allDiseases.map(d => (
              <option key={d} value={d}>{d.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</option>
            ))}
          </select>
        </div>

        <div className="text-xs text-gray-400 ml-auto">
          {filtered.length} of {rows.length} drugs
        </div>
      </div>

      {/* Table — Generic column removed */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600 border-b border-gray-200">
              <tr>
                {[
                  { label: "Drug Name",   key: "name"      as SortKey },
                  { label: "Dose",        key: "dose"      as SortKey },
                  { label: "Price/unit",  key: "price"     as SortKey },
                  { label: "In Stock",    key: "stock"     as SortKey },
                  { label: "Reorder Pt.", key: "reorder"   as SortKey },
                  { label: "Days Cover",  key: "days_cover"as SortKey },
                  { label: "Status",      key: "status"    as SortKey },
                  { label: "For Diseases", key: null },
                ].map(col => (
                  <th
                    key={col.label}
                    onClick={() => col.key && toggleSort(col.key)}
                    className={`px-4 py-3 text-left font-medium text-xs uppercase tracking-wider ${col.key ? "cursor-pointer hover:bg-gray-100 select-none" : ""}`}
                  >
                    <div className="flex items-center gap-1.5">
                      {col.label}
                      {col.key && <SortIcon col={col.key} />}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 8 }).map((__, j) => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded w-3/4" /></td>
                    ))}
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                    No drugs match your filters.
                  </td>
                </tr>
              ) : (
                <AnimatePresence>
                  {filtered.map((row, idx) => (
                    <motion.tr
                      key={row.id || row.name}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ delay: idx * 0.015 }}
                      className="hover:bg-gray-50/60 transition-colors"
                    >
                      <td className="px-4 py-3 font-medium text-gray-900">{row.name}</td>
                      <td className="px-4 py-3 text-gray-500">{row.dose}</td>
                      <td className="px-4 py-3 text-gray-700 font-medium">₹{row.price.toFixed(2)}</td>
                      <td className="px-4 py-3 font-semibold text-gray-900">{row.stock.toLocaleString("en-IN")}</td>
                      <td className="px-4 py-3 text-gray-500">{row.reorder.toLocaleString("en-IN")}</td>
                      <td className={`px-4 py-3 font-semibold ${
                        row.days_cover < 7  ? "text-red-600"
                        : row.days_cover < 30 ? "text-amber-600"
                        : "text-emerald-600"
                      }`}>
                        {row.days_cover}d
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${row.status.color}`}>
                          {row.status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {row.diseases.slice(0, 2).map((d: string) => (
                            <span key={d} className="text-[10px] bg-blue-50 text-blue-600 border border-blue-100 px-1.5 py-0.5 rounded-full">
                              {d.replace(/_/g, " ")}
                            </span>
                          ))}
                          {row.diseases.length > 2 && (
                            <span className="text-[10px] text-gray-400">+{row.diseases.length - 2}</span>
                          )}
                        </div>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
