"use client";

import { useState } from "react";
import useSWR from "swr";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Eye, Hand, CheckCircle, XCircle, Clock, MessageCircle,
  Phone, Send, Package, Bot, ShieldCheck, FileText, Calendar,
  Building2, Printer, ChevronDown, ChevronUp, AlertTriangle
} from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());
const HOSPITAL_ID = "a4174db7-8319-4494-9585-c4777f408ed9";

type Mode = "autonomous" | "oversight" | "manual";

const MODES = [
  {
    id: "autonomous" as Mode,
    icon: Bot,
    label: "Full Autonomy",
    tagline: "AI handles end-to-end",
    description: "Pharmasense auto-creates, approves and dispatches POs to vendors. Zero manual steps.",
    color: "from-violet-600 to-purple-700",
    badgeColor: "bg-violet-100 text-violet-700 border-violet-200",
  },
  {
    id: "oversight" as Mode,
    icon: MessageCircle,
    label: "WhatsApp Oversight",
    tagline: "Notified, you decide",
    description: "AI recommends orders and sends you a WhatsApp alert. Reply APPROVE or REJECT from your phone.",
    color: "from-emerald-600 to-green-700",
    badgeColor: "bg-emerald-100 text-emerald-700 border-emerald-200",
  },
  {
    id: "manual" as Mode,
    icon: Hand,
    label: "Full Control",
    tagline: "You approve everything",
    description: "All orders created as drafts. Review and approve each one in this dashboard before dispatch.",
    color: "from-gray-800 to-gray-900",
    badgeColor: "bg-gray-100 text-gray-700 border-gray-200",
  },
];

const STATUS_STYLE: Record<string, { bg: string; label: string }> = {
  AUTO_APPROVED:    { bg: "bg-violet-100 text-violet-700",  label: "Auto-Dispatched" },
  PENDING_APPROVAL: { bg: "bg-amber-100 text-amber-700",    label: "Pending Approval" },
  APPROVED:         { bg: "bg-emerald-100 text-emerald-700",label: "Approved" },
  REJECTED:         { bg: "bg-red-100 text-red-700",        label: "Rejected" },
  DRAFT:            { bg: "bg-gray-100 text-gray-700",      label: "Draft" },
};

/** Renders a visual Purchase Order document */
function PODocument({
  orders, hospitalName, mode, createdAt, totalCost
}: {
  orders: any[];
  hospitalName: string;
  mode: Mode;
  createdAt: string;
  totalCost: number;
}) {
  const poNumber = `PO-${new Date().getFullYear()}-${String(Math.floor(Math.random()*9000)+1000)}`;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border-2 border-gray-200 rounded-2xl overflow-hidden shadow-lg"
    >
      {/* PO Header */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-800 px-6 py-5 flex items-start justify-between">
        <div>
          <div className="text-white font-black text-xl tracking-tight">pharmasense</div>
          <div className="text-gray-400 text-xs mt-0.5">AI-Powered Procurement System</div>
        </div>
        <div className="text-right">
          <div className="text-gray-300 text-xs font-mono">PURCHASE ORDER</div>
          <div className="text-white font-bold text-lg font-mono">{poNumber}</div>
          <div className="text-gray-400 text-xs mt-0.5">{new Date(createdAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</div>
        </div>
      </div>

      {/* Billing info */}
      <div className="grid grid-cols-2 gap-6 px-6 py-4 border-b border-gray-100 bg-gray-50">
        <div>
          <div className="text-[10px] text-gray-400 font-semibold uppercase mb-1">Bill To</div>
          <div className="font-semibold text-gray-900 text-sm">{hospitalName}</div>
          <div className="text-xs text-gray-500 mt-0.5">Govt. Procurement Division</div>
          <div className="text-xs text-gray-500">India — GST Registered</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-400 font-semibold uppercase mb-1">Dispatch Mode</div>
          <div className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full ${
            mode === "autonomous" ? "bg-violet-100 text-violet-700" :
            mode === "oversight"  ? "bg-emerald-100 text-emerald-700" :
            "bg-gray-100 text-gray-700"
          }`}>
            {mode === "autonomous" ? <Bot className="w-3 h-3" /> : mode === "oversight" ? <MessageCircle className="w-3 h-3" /> : <Hand className="w-3 h-3" />}
            {mode === "autonomous" ? "Full Autonomy" : mode === "oversight" ? "WhatsApp Oversight" : "Manual Approval"}
          </div>
          <div className="text-xs text-gray-500 mt-2 flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            Generated {new Date(createdAt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
      </div>

      {/* Line items */}
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider border-b border-gray-200">
          <tr>
            <th className="px-5 py-3 text-left">#</th>
            <th className="px-5 py-3 text-left">Drug / Item</th>
            <th className="px-5 py-3 text-right">Qty</th>
            <th className="px-5 py-3 text-right">Unit Price</th>
            <th className="px-5 py-3 text-right">Total</th>
            <th className="px-5 py-3 text-center">Priority</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {orders.map((o: any, i: number) => {
            const unitPrice = o.order_cost_inr / o.order_quantity;
            return (
              <tr key={i} className="hover:bg-gray-50/50">
                <td className="px-5 py-3 text-gray-400 text-xs font-mono">{String(i+1).padStart(2,"0")}</td>
                <td className="px-5 py-3">
                  <div className="font-medium text-gray-900">{o.drug_name}</div>
                  <div className="text-xs text-gray-400 mt-0.5 truncate max-w-[200px]">{o.reason}</div>
                </td>
                <td className="px-5 py-3 text-right font-semibold text-gray-800">{o.order_quantity?.toLocaleString("en-IN")}</td>
                <td className="px-5 py-3 text-right text-gray-600">₹{unitPrice.toFixed(2)}</td>
                <td className="px-5 py-3 text-right font-bold text-gray-900">₹{o.order_cost_inr?.toLocaleString("en-IN")}</td>
                <td className="px-5 py-3 text-center">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    o.urgency === "HIGH"   ? "bg-red-100 text-red-700"   :
                    o.urgency === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                    "bg-gray-100 text-gray-600"
                  }`}>{o.urgency}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot className="border-t-2 border-gray-200 bg-gray-50">
          <tr>
            <td colSpan={4} className="px-5 py-3 text-right text-sm font-semibold text-gray-700">Total Amount:</td>
            <td className="px-5 py-3 text-right text-lg font-black text-gray-900">₹{totalCost.toLocaleString("en-IN")}</td>
            <td />
          </tr>
        </tfoot>
      </table>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
        <div className="text-[11px] text-gray-400">
          Generated by Pharmasense AI · ST-GNN + TFT ensemble · Subject to pharmacist review
        </div>
        <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold">
          <ShieldCheck className="w-3.5 h-3.5" />
          ICMR Compliant
        </div>
      </div>
    </motion.div>
  );
}

export default function PurchaseOrdersPage() {
  const [mode,       setMode]       = useState<Mode>("manual");
  const [phone,      setPhone]      = useState("+91");
  const [showPhone,  setShowPhone]  = useState(false);
  const [creating,   setCreating]   = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [generatedPO, setGeneratedPO] = useState<{ orders: any[]; createdAt: string; totalCost: number } | null>(null);
  const [showPO,     setShowPO]     = useState(false);

  const { data: forecastData } = useSWR(`/api/v1/forecast/hospital/${HOSPITAL_ID}`, fetcher);
  const { data: hospData }     = useSWR(`/api/v1/hospitals/${HOSPITAL_ID}`, fetcher);
  const { data: ordersData, mutate: refreshOrders } = useSWR(
    `/api/v1/orders/hospital/${HOSPITAL_ID}`,
    fetcher,
    { refreshInterval: 3000 }   // poll every 3s so WA replies reflect fast
  );

  const pendingOrders: any[]  = forecastData?.orders ?? [];
  const existingOrders: any[] = ordersData?.orders ?? [];
  const hospitalName = hospData?.name ?? "Your Hospital";
  const totalCost = pendingOrders.reduce((s: number, o: any) => s + o.order_cost_inr, 0);

  async function handleCreateAllOrders() {
    if (mode === "oversight" && !phone.match(/^\+?\d{10,14}$/)) {
      alert("Please enter a valid WhatsApp number (e.g. +919876543210)");
      return;
    }
    setCreating(true);
    try {
      const results = [];
      for (const order of pendingOrders) {
        const res = await fetch("/api/v1/orders/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            hospital_id:   HOSPITAL_ID,
            drug_id:       order.drug_id,
            drug_name:     order.drug_name,
            quantity:      order.order_quantity,
            unit_cost_inr: order.order_cost_inr / order.order_quantity,
            reason:        order.reason,
            mode,
            phone_number:  mode === "oversight" ? phone : undefined,
          }),
        });
        const json = await res.json();
        results.push(json);
      }

      // Show the PO document
      setGeneratedPO({ orders: pendingOrders, createdAt: new Date().toISOString(), totalCost });
      setShowPO(true);

      setSuccessMsg(
        mode === "autonomous" ? "✅ All orders auto-approved and dispatched to vendors!" :
        mode === "oversight"  ? `📱 WhatsApp alerts sent to ${phone}. Awaiting your replies.` :
        "📋 All orders created as drafts. Review and approve below."
      );
      refreshOrders();
    } finally {
      setCreating(false);
      setTimeout(() => setSuccessMsg(""), 8000);
    }
  }

  async function approveOrder(orderId: string, approved: boolean) {
    await fetch(`/api/v1/orders/${orderId}/approve`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, notes: approved ? "Approved by pharmacist." : "Rejected by pharmacist." }),
    });
    refreshOrders();
  }

  const activeModeConfig = MODES.find(m => m.id === mode)!;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">

      {/* Mode selector */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Automation Mode</h2>
        <p className="text-sm text-gray-500 mb-4">
          Choose how Pharmasense handles purchase orders for your facility.
        </p>
        <div className="grid md:grid-cols-3 gap-4">
          {MODES.map(m => {
            const Icon = m.icon;
            const isActive = mode === m.id;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setShowPhone(m.id === "oversight"); }}
                className={`relative text-left rounded-2xl border-2 p-5 transition-all ${
                  isActive ? "border-[#111111] shadow-lg" : "border-gray-200 hover:border-gray-300 hover:shadow-sm"
                }`}
              >
                <div className={`inline-flex p-2 rounded-xl bg-gradient-to-br ${m.color} mb-3`}>
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <div className="font-semibold text-gray-900 mb-0.5">{m.label}</div>
                <div className={`text-xs font-medium px-2 py-0.5 rounded-full border inline-block mb-2 ${m.badgeColor}`}>{m.tagline}</div>
                <p className="text-xs text-gray-500 leading-relaxed">{m.description}</p>
                {isActive && (
                  <div className="absolute top-3 right-3">
                    <CheckCircle className="w-5 h-5 text-[#111111]" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* WhatsApp input */}
      <AnimatePresence>
        {showPhone && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 space-y-3"
          >
            <div className="flex items-start gap-3">
              <Phone className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-medium text-emerald-800 mb-1">WhatsApp Number for Alerts</div>
                <input
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  placeholder="+919876543210"
                  className="w-full sm:w-72 px-3 py-2 text-sm border border-emerald-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-400"
                />
              </div>
            </div>
            <div className="border-t border-emerald-200 pt-3 grid sm:grid-cols-3 gap-3 text-xs text-emerald-700">
              <div>
                <div className="font-semibold mb-1">📋 Step 1 — Join Sandbox</div>
                <div className="text-emerald-600">Text <code className="bg-emerald-100 px-1 rounded">join &lt;keyword&gt;</code> to <strong>+14155238886</strong> on WhatsApp first.</div>
              </div>
              <div>
                <div className="font-semibold mb-1">💬 Step 2 — Reply to act</div>
                <div className="text-emerald-600">Reply <code className="bg-emerald-100 px-1 rounded">APPROVE XYZ</code> or <code className="bg-emerald-100 px-1 rounded">REJECT XYZ</code> to any alert message.</div>
              </div>
              <div>
                <div className="font-semibold mb-1">👍 Or react with emoji</div>
                <div className="text-emerald-600">React with 👍 on any PO alert to approve it instantly. Requires webhook — run <code className="bg-emerald-100 px-1 rounded">ngrok http 8000</code> and set URL in Twilio console.</div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* AI Recommendations table */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">AI-Recommended Orders</h2>
            <p className="text-sm text-gray-500">Based on active disease risk and real inventory levels from Supabase.</p>
          </div>
          {pendingOrders.length > 0 && (
            <button
              onClick={handleCreateAllOrders}
              disabled={creating}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all bg-gradient-to-br ${activeModeConfig.color} text-white hover:opacity-90 disabled:opacity-60 shadow-sm`}
            >
              {creating ? (
                <span className="animate-spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
              ) : mode === "autonomous" ? <Zap className="w-4 h-4" /> :
                 mode === "oversight"  ? <Send className="w-4 h-4" /> :
                                         <FileText className="w-4 h-4" />}
              {mode === "autonomous" ? "Auto-Dispatch All" :
               mode === "oversight"  ? "Send WhatsApp Alerts" :
               "Generate Purchase Order"}
            </button>
          )}
        </div>

        {/* Success banner */}
        <AnimatePresence>
          {successMsg && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-4 flex items-center gap-3 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800"
            >
              <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
              {successMsg}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">Drug</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Est. Cost</th>
                <th className="px-4 py-3 text-center">Urgency</th>
                <th className="px-4 py-3 text-left">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {!forecastData ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {[1,2,3,4,5].map(j => (
                      <td key={j} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : pendingOrders.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-gray-400">
                    No orders recommended. Inventory levels are healthy.
                  </td>
                </tr>
              ) : (
                pendingOrders.map((order, i) => (
                  <tr key={i} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      <div className="flex items-center gap-2">
                        <Package className="w-4 h-4 text-gray-400 shrink-0" />
                        {order.drug_name}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-right">{order.order_quantity?.toLocaleString("en-IN")}</td>
                    <td className="px-4 py-3 font-semibold text-gray-900 text-right">₹{order.order_cost_inr?.toLocaleString("en-IN")}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                        order.urgency === "HIGH"   ? "bg-red-100 text-red-700" :
                        order.urgency === "MEDIUM" ? "bg-amber-100 text-amber-700" :
                        "bg-gray-100 text-gray-700"
                      }`}>
                        {order.urgency}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-[220px]">{order.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {pendingOrders.length > 0 && (
            <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex justify-between text-sm">
              <span className="text-gray-500">{pendingOrders.length} recommended orders</span>
              <span className="font-semibold text-gray-900">
                Total: ₹{totalCost.toLocaleString("en-IN")}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Generated PO Document */}
      <AnimatePresence>
        {showPO && generatedPO && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-gray-700" />
                <h2 className="text-lg font-semibold text-gray-900">Generated Purchase Order</h2>
              </div>
              <button
                onClick={() => setShowPO(!showPO)}
                className="text-sm text-gray-500 flex items-center gap-1 hover:text-gray-800"
              >
                {showPO ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                {showPO ? "Collapse" : "Expand"}
              </button>
            </div>
            <PODocument
              orders={generatedPO.orders}
              hospitalName={hospitalName}
              mode={mode}
              createdAt={generatedPO.createdAt}
              totalCost={generatedPO.totalCost}
            />
          </div>
        )}
      </AnimatePresence>

      {/* Existing orders / approval queue */}
      {existingOrders.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Order History & Pending Approvals</h2>
          <div className="space-y-3">
            {existingOrders.map((order: any) => {
              const s = STATUS_STYLE[order.status] ?? { bg: "bg-gray-100 text-gray-700", label: order.status };
              return (
                <div key={order.id} className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-4 shadow-sm">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-gray-900">{order.drug_name}</span>
                      <span className="text-xs text-gray-400 font-mono">#{order.id}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {order.quantity?.toLocaleString("en-IN")} units · ₹{order.total_cost_inr?.toLocaleString("en-IN")} · {order.note}
                    </div>
                  </div>

                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${s.bg}`}>
                    {s.label}
                  </span>

                  {(order.status === "DRAFT" || order.status === "PENDING_APPROVAL") ? (
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => approveOrder(order.id, true)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
                      >
                        <CheckCircle className="w-3.5 h-3.5" /> Approve
                      </button>
                      <button
                        onClick={() => approveOrder(order.id, false)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Reject
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
