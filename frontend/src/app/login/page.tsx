"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, User, ChevronDown, ChevronUp, Eye, EyeOff } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

// ─── Demo accounts — 5 real-ish facilities ─────────────────────────────────
const DEMO_ACCOUNTS = [
  {
    email:    "rajivgandhi@pharmasense.in",
    password: "demo@123",
    facility: "Rajiv Gandhi Govt. General Hospital",
    city:     "Chennai, Tamil Nadu",
    role:     "District Hospital · 2600 beds",
    hospitalId: "a4174db7-8319-4494-9585-c4777f408ed9",
  },
  {
    email:    "aiims.delhi@pharmasense.in",
    password: "demo@123",
    facility: "AIIMS New Delhi",
    city:     "New Delhi, Delhi",
    role:     "Tertiary Referral Centre · 2484 beds",
    hospitalId: "b1234567-0000-0000-0000-000000000001",
  },
  {
    email:    "kem.mumbai@pharmasense.in",
    password: "demo@123",
    facility: "KEM Hospital",
    city:     "Mumbai, Maharashtra",
    role:     "Municipal Hospital · 1800 beds",
    hospitalId: "b1234567-0000-0000-0000-000000000002",
  },
  {
    email:    "victoria.bangalore@pharmasense.in",
    password: "demo@123",
    facility: "Victoria Hospital",
    city:     "Bengaluru, Karnataka",
    role:     "District Hospital · 1260 beds",
    hospitalId: "b1234567-0000-0000-0000-000000000003",
  },
  {
    email:    "pgimer.chandigarh@pharmasense.in",
    password: "demo@123",
    facility: "PGIMER Chandigarh",
    city:     "Chandigarh, Punjab",
    role:     "Post-Graduate Institute · 2204 beds",
    hospitalId: "b1234567-0000-0000-0000-000000000004",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email,       setEmail]       = useState("");
  const [password,    setPassword]    = useState("");
  const [showPass,    setShowPass]    = useState(false);
  const [error,       setError]       = useState("");
  const [showCreds,   setShowCreds]   = useState(false);
  const [loading,     setLoading]     = useState(false);

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Small delay for UX
    setTimeout(() => {
      const account = DEMO_ACCOUNTS.find(
        a => a.email.toLowerCase() === email.toLowerCase() && a.password === password
      );
      if (account) {
        // Store session
        localStorage.setItem("ps_user", JSON.stringify({
          email:      account.email,
          facility:   account.facility,
          city:       account.city,
          hospitalId: account.hospitalId,
        }));
        router.push("/overview");
      } else {
        setError("Invalid email or password. Use one of the demo accounts below.");
        setLoading(false);
      }
    }, 600);
  }

  function fillDemo(acc: typeof DEMO_ACCOUNTS[0]) {
    setEmail(acc.email);
    setPassword(acc.password);
    setError("");
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f8f8f8] p-6">
      <div className="w-full max-w-md">

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden"
        >
          <div className="p-8">
            {/* Title */}
            <h1 className="text-2xl font-bold tracking-tight text-[#111111] mb-1">Login</h1>
            <p className="text-gray-500 text-sm mb-8">
              Sign in to access your facility's Pharmasense dashboard.
            </p>

            <form className="space-y-5" onSubmit={handleLogin}>
              {/* Email */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="w-4 h-4 text-gray-400" />
                  </div>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10 focus:bg-white transition-all text-sm"
                    placeholder="you@pharmasense.in"
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="w-4 h-4 text-gray-400" />
                  </div>
                  <input
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    className="w-full pl-10 pr-10 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10 focus:bg-white transition-all text-sm"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(p => !p)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                  >
                    {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Error */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-[#111111] text-white text-sm font-semibold hover:bg-black transition-colors flex items-center justify-center gap-2 rounded-lg disabled:opacity-60"
                >
                  {loading ? (
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : "Access Dashboard"}
                </button>
              </div>
            </form>
          </div>

          {/* Demo credentials accordion */}
          <div className="border-t border-gray-100">
            <button
              onClick={() => setShowCreds(v => !v)}
              className="w-full px-6 py-3 flex items-center justify-between text-sm text-gray-500 hover:bg-gray-50 transition-colors"
            >
              <span className="font-medium">Demo Accounts ({DEMO_ACCOUNTS.length} facilities)</span>
              {showCreds ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            <AnimatePresence>
              {showCreds && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="px-4 pb-4 space-y-2">
                    {DEMO_ACCOUNTS.map((acc, i) => (
                      <button
                        key={i}
                        onClick={() => fillDemo(acc)}
                        className="w-full text-left px-3 py-2.5 rounded-lg border border-gray-200 hover:border-gray-900 hover:bg-gray-50 transition-all group"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="font-semibold text-gray-900 text-sm">{acc.facility}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{acc.city} · {acc.role}</div>
                            <div className="text-[11px] text-gray-400 font-mono mt-1">{acc.email}</div>
                          </div>
                          <span className="text-[10px] font-bold text-gray-400 group-hover:text-gray-900 mt-1 shrink-0">Fill →</span>
                        </div>
                      </button>
                    ))}
                    <p className="text-[11px] text-gray-400 px-1 pt-1">All accounts use password: <code className="font-mono">demo@123</code></p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Brand footer */}
        <div className="text-center mt-10">
          <span className="text-2xl font-black tracking-tighter text-gray-400" style={{ letterSpacing: "-0.05em" }}>
            pharmasense
          </span>
          <div className="text-xs text-gray-400 mt-1">AI-Powered Pharmaceutical Supply Intelligence</div>
        </div>
      </div>
    </div>
  );
}
