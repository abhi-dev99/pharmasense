"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Activity, ShieldAlert, PackageCheck, Zap, Database, Lock } from "lucide-react";
import { useRef } from "react";
import { IndiaHeatmap } from "@/components/shared/IndiaHeatmap";

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Parallax effects for the hero heatmap
  const mapY = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const mapOpacity = useTransform(scrollYProgress, [0, 0.3], [1, 0]);

  // Card reveal effects
  const card1Y = useTransform(scrollYProgress, [0.1, 0.4], [100, 0]);
  const card1Opacity = useTransform(scrollYProgress, [0.1, 0.4], [0, 1]);
  
  const card2Y = useTransform(scrollYProgress, [0.2, 0.5], [100, 0]);
  const card2Opacity = useTransform(scrollYProgress, [0.2, 0.5], [0, 1]);

  const card3Y = useTransform(scrollYProgress, [0.3, 0.6], [100, 0]);
  const card3Opacity = useTransform(scrollYProgress, [0.3, 0.6], [0, 1]);

  return (
    <div ref={containerRef} className="min-h-[200vh] bg-[#fdfdfd] text-[#333333] selection:bg-black selection:text-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-4 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="text-2xl tracking-tighter text-[#404040] select-none" style={{ letterSpacing: "-0.05em" }}>
          pharma<span className="font-bold">sense</span>
        </div>
        <div className="flex gap-4">
          <Link 
            href="/login" 
            className="px-6 py-2.5 text-sm font-medium bg-[#111111] text-white hover:bg-black rounded-none transition-colors flex items-center gap-2 shadow-sm"
          >
            Login <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="min-h-screen flex items-center justify-center bg-[#fafafa] pt-20 px-6 md:px-12">
        <div className="max-w-7xl w-full grid lg:grid-cols-2 gap-12 items-center">
          
          {/* Text Column */}
          <div className="z-10 text-left max-w-2xl text-[#111111]">
            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="text-5xl md:text-7xl font-bold tracking-tighter leading-[1.05]"
              style={{ letterSpacing: "-0.04em" }}
            >
              Predicting shortages <br/>
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#FF416C] to-[#FF4B2B]">
                before they happen.
              </span>
            </motion.h1>
            <motion.p 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4, duration: 0.8 }}
              className="mt-6 text-xl md:text-2xl text-gray-500 font-light tracking-tight"
            >
              Enterprise pharmaceutical supply chain intelligence for India's 641 districts and 25,000 public health facilities.
            </motion.p>
          </div>

          {/* Map Column */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1, delay: 0.2, ease: "easeOut" }}
            className="w-full relative z-20"
          >
            <IndiaHeatmap />
          </motion.div>
        </div>
      </div>

      {/* Shuffling Cards Section */}
      <div className="relative z-20 bg-[#fdfdfd] min-h-screen py-32 px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-6xl font-bold tracking-tight" style={{ letterSpacing: "-0.03em" }}>
              <motion.span
                initial={{ backgroundColor: "transparent", color: "inherit", padding: "0" }}
                whileInView={{ backgroundColor: "#111111", color: "#ffffff", padding: "0 16px" }}
                transition={{ duration: 0.4, ease: "easeInOut" }}
                viewport={{ once: false, margin: "-100px" }}
                className="inline-block"
              >
                Full-loop automation.
              </motion.span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-8 border border-gray-200 rounded-xl bg-white shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group cursor-default">
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full -mr-16 -mt-16 transition-transform duration-500 group-hover:scale-150"></div>
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-blue-500/20 text-white relative z-10">
                <ShieldAlert className="w-7 h-7" />
              </div>
              <h3 className="text-2xl font-bold mb-2 relative z-10">ICMR Translation Layer</h3>
              <p className="text-gray-500 text-sm relative z-10 mb-4 font-medium">Converts outbreaks to exact SKU volumes.</p>
              
              <div className="grid grid-rows-[0fr] group-hover:grid-rows-[1fr] transition-all duration-300 ease-in-out">
                <div className="overflow-hidden">
                  <ul className="space-y-2 text-gray-500 relative z-10 text-sm border-t border-gray-100 pt-4">
                    <li className="flex items-start gap-2"><span className="text-blue-500 font-bold">•</span> Ingests live Epidemic data streams</li>
                    <li className="flex items-start gap-2"><span className="text-blue-500 font-bold">•</span> Maps standard ICMR treatment protocols</li>
                    <li className="flex items-start gap-2"><span className="text-blue-500 font-bold">•</span> e.g., 1 Dengue case = specific IV fluid units</li>
                  </ul>
                </div>
              </div>
            </div>
            
            <div className="p-8 border border-gray-200 rounded-xl bg-white shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group cursor-default">
              <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full -mr-16 -mt-16 transition-transform duration-500 group-hover:scale-150"></div>
              <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-emerald-500/20 text-white relative z-10">
                <PackageCheck className="w-7 h-7" />
              </div>
              <h3 className="text-2xl font-bold mb-2 relative z-10">Adjacency Pre-Stocking</h3>
              <p className="text-gray-500 text-sm relative z-10 mb-4 font-medium">Proactively stocks before disease crosses borders.</p>

              <div className="grid grid-rows-[0fr] group-hover:grid-rows-[1fr] transition-all duration-300 ease-in-out">
                <div className="overflow-hidden">
                  <ul className="space-y-2 text-gray-500 relative z-10 text-sm border-t border-gray-100 pt-4">
                    <li className="flex items-start gap-2"><span className="text-emerald-500 font-bold">•</span> Monitors neighbouring district outbreaks</li>
                    <li className="flex items-start gap-2"><span className="text-emerald-500 font-bold">•</span> Flags rising cross-border infection vectors</li>
                    <li className="flex items-start gap-2"><span className="text-emerald-500 font-bold">•</span> Auto-generates proactive Purchase Orders</li>
                  </ul>
                </div>
              </div>
            </div>
            
            <div className="p-8 border border-gray-200 rounded-xl bg-white shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden group cursor-default">
              <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/10 rounded-full -mr-16 -mt-16 transition-transform duration-500 group-hover:scale-150"></div>
              <div className="w-14 h-14 bg-gradient-to-br from-orange-500 to-red-600 rounded-xl flex items-center justify-center mb-6 shadow-lg shadow-orange-500/20 text-white relative z-10">
                <Database className="w-7 h-7" />
              </div>
              <h3 className="text-2xl font-bold mb-2 relative z-10">Stock Rebalancing</h3>
              <p className="text-gray-500 text-sm relative z-10 mb-4 font-medium">Digitally redirects surplus inventory to high-risk zones.</p>

              <div className="grid grid-rows-[0fr] group-hover:grid-rows-[1fr] transition-all duration-300 ease-in-out">
                <div className="overflow-hidden">
                  <ul className="space-y-2 text-gray-500 relative z-10 text-sm border-t border-gray-100 pt-4">
                    <li className="flex items-start gap-2"><span className="text-orange-500 font-bold">•</span> Identifies overstocked health facilities</li>
                    <li className="flex items-start gap-2"><span className="text-orange-500 font-bold">•</span> Re-routes surplus inventory dynamically</li>
                    <li className="flex items-start gap-2"><span className="text-orange-500 font-bold">•</span> Eliminates waste and balances supply chains</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* More Content Section */}
          <div className="mt-32 pt-24 border-t border-gray-200">
            <div className="grid md:grid-cols-2 gap-16 items-center">
              <div>
                <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6" style={{ letterSpacing: "-0.03em" }}>
                  Built for scale.
                </h2>
                <p className="text-gray-500 text-lg leading-relaxed mb-8">
                  Pharmasense is designed to handle the scale of India's public health infrastructure. It continuously syncs with HMIS data to predict localized outbreaks and adjust stock requirements automatically.
                </p>
                <ul className="space-y-4">
                  <li className="flex items-center gap-3 text-[#111111] font-medium">
                    <Zap className="w-5 h-5 text-gray-400" /> Live Temporal Fusion Transformer (TFT) predictions
                  </li>
                  <li className="flex items-center gap-3 text-[#111111] font-medium">
                    <Database className="w-5 h-5 text-gray-400" /> Automated inventory redistribution
                  </li>
                  <li className="flex items-center gap-3 text-[#111111] font-medium">
                    <Lock className="w-5 h-5 text-gray-400" /> Enterprise-grade Role Based Access
                  </li>
                </ul>
              </div>
              <div className="bg-[#f5f5f5] h-96 w-full flex items-center justify-center p-8 border border-gray-200 shadow-inner rounded-xl">
                 <div className="text-center">
                    <Activity className="w-12 h-12 text-[#2b2b2b] mx-auto mb-4" />
                    <p className="text-gray-500 font-medium">Real-time telemetry active</p>
                 </div>
              </div>
            </div>
          </div>

          {/* Trusted Sources Marquee */}
          <div className="mt-32 py-16 border-y border-gray-200 bg-[#fdfdfd] overflow-hidden flex flex-col items-center">
            <p className="text-sm uppercase tracking-widest text-gray-400 font-semibold mb-8 text-center">Built on trusted intelligence sources</p>
            <div className="w-full flex relative overflow-hidden group">
              <div className="flex whitespace-nowrap animate-marquee items-center gap-16 px-8">
                {/* Original Set */}
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">HMIS Data</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">IDSP Outbreak Signals</span>
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-500 to-teal-500">ICMR Treatment Guidelines</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">IMD Weather Telemetry</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">DVDMS Inventory</span>
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-orange-500 to-red-500">NHM Directives</span>
                {/* Duplicated Set for Seamless Loop */}
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">HMIS Data</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">IDSP Outbreak Signals</span>
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-500 to-teal-500">ICMR Treatment Guidelines</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">IMD Weather Telemetry</span>
                <span className="text-2xl font-bold font-serif tracking-tight text-gray-400">DVDMS Inventory</span>
                <span className="text-2xl font-bold font-serif tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-orange-500 to-red-500">NHM Directives</span>
              </div>
            </div>
          </div>

          {/* Bottom CTA */}
          <div className="my-32 bg-[#111111] rounded-2xl p-12 md:p-24 text-center text-white">
            <h2 className="text-4xl md:text-6xl font-bold tracking-tight mb-6" style={{ letterSpacing: "-0.03em" }}>
              Ready to modernize?
            </h2>
            <p className="text-gray-400 text-xl mb-10 max-w-2xl mx-auto font-light">
              Log in to the dashboard to view real-time risk assessments and pending automated purchase orders for your jurisdiction.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/login" className="w-full sm:w-auto px-8 py-4 bg-white text-black text-sm font-medium hover:bg-gray-100 transition-colors rounded-full flex items-center justify-center gap-2">
                Open Dashboard <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Smart Footer */}
      <footer className="border-t border-gray-200 bg-white py-12 px-6 md:px-12">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8">
          <div className="md:col-span-2">
            <div className="font-bold text-3xl tracking-tighter text-[#404040] select-none mb-4" style={{ letterSpacing: "-0.05em" }}>
              pharma<span className="font-bold">sense</span>
            </div>
            <p className="text-gray-500 text-sm max-w-sm">
              Enterprise predictive analytics for India's public health supply chain. Developed to anticipate shortages before they happen.
            </p>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-4 text-sm">Platform</h4>
            <ul className="space-y-3 text-sm text-gray-500">
              <li><Link href="/" className="hover:text-black transition-colors">Home</Link></li>
              <li><Link href="/overview" className="hover:text-black transition-colors">Dashboard</Link></li>
              <li><Link href="/login" className="hover:text-black transition-colors">Login</Link></li>
              <li><a href="https://github.com/AGTechathon-2-0/ragebaiters/" target="_blank" rel="noopener noreferrer" className="hover:text-black transition-colors flex items-center gap-1">Open Source <ArrowRight className="w-3 h-3"/></a></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 mb-4 text-sm">Legal & Compliance</h4>
            <ul className="space-y-3 text-sm text-gray-500">
              <li><span className="text-gray-400">NHA Data Protection (Pending)</span></li>
              <li><span className="text-gray-400">ICMR Guidelines (Pending)</span></li>
            </ul>
          </div>
        </div>
        <div className="max-w-7xl mx-auto mt-12 pt-8 border-t border-gray-100 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-gray-400">
          <p>© 2026 Pharmasense. All rights reserved.</p>
          <div className="flex gap-6">
            <span className="text-emerald-600 font-medium flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-emerald-500"></span> System Status: Operational</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
