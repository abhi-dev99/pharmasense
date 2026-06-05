"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Building, Lock, User, KeyRound } from "lucide-react";
import { motion } from "framer-motion";

export default function LoginPage() {
  const [role, setRole] = useState<"hospital" | "state">("hospital");

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fdfdfd] p-6 relative">
      <div className="w-full max-w-md relative z-10">
        
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-black transition-colors mb-8">
          <ArrowLeft className="w-4 h-4" /> Back to home
        </Link>

        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="bg-white border border-gray-200 shadow-sm"
        >
          <div className="p-8">
            <h1 className="text-2xl font-bold tracking-tight text-[#111111] mb-2">
              pharma<span className="font-bold">sense</span>
            </h1>
            <p className="text-gray-500 text-sm mb-8">
              Enter your credentials to access your jurisdictional dashboard.
            </p>

            {/* Role Toggle */}
            <div className="flex p-1 bg-gray-100 mb-8 border border-gray-200">
              <button 
                onClick={() => setRole("hospital")}
                className={`flex-1 py-2 px-4 text-sm font-medium flex items-center justify-center gap-2 transition-all ${
                  role === "hospital" ? "bg-white text-black shadow-sm border border-gray-200" : "text-gray-500 hover:text-gray-700 border border-transparent"
                }`}
              >
                <Building className="w-4 h-4" /> Facility Level
              </button>
              <button 
                onClick={() => setRole("state")}
                className={`flex-1 py-2 px-4 text-sm font-medium flex items-center justify-center gap-2 transition-all ${
                  role === "state" ? "bg-white text-black shadow-sm border border-gray-200" : "text-gray-500 hover:text-gray-700 border border-transparent"
                }`}
              >
                <KeyRound className="w-4 h-4" /> State Admin
              </button>
            </div>

            <form className="space-y-5" onSubmit={(e) => e.preventDefault()}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">
                  {role === "hospital" ? "Facility ID / Email" : "Admin Email"}
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="w-4 h-4 text-gray-400" />
                  </div>
                  <input 
                    type="email" 
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 focus:outline-none focus:ring-1 focus:ring-black focus:bg-white transition-all text-sm rounded-none"
                    placeholder={role === "hospital" ? "MH-PUN-042@facility.gov.in" : "admin@nhm.gov.in"}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-gray-700">Password</label>
                  <a href="#" className="text-xs text-blue-600 hover:underline">Forgot?</a>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="w-4 h-4 text-gray-400" />
                  </div>
                  <input 
                    type="password" 
                    className="w-full pl-10 pr-4 py-2.5 bg-gray-50 border border-gray-200 focus:outline-none focus:ring-1 focus:ring-black focus:bg-white transition-all text-sm rounded-none"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <div className="pt-4">
                <Link href="/overview" className="w-full py-3 bg-[#111111] text-white text-sm font-medium hover:bg-black transition-colors flex items-center justify-center gap-2 rounded-none">
                  Access Dashboard
                </Link>
              </div>
            </form>
          </div>
        </motion.div>
        
        <div className="text-center mt-12 text-sm text-gray-400 font-bold tracking-tight">
          pharma<span className="font-bold">sense</span>
        </div>
      </div>
    </div>
  );
}
