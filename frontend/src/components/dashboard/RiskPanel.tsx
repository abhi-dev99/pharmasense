"use client";

import useSWR from 'swr';
import { motion } from 'framer-motion';
import { AlertTriangle, TrendingUp, TrendingDown, Activity } from 'lucide-react';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface RiskScore {
  disease: string;
  score: number;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  predicted_cases: number;
  baseline_cases: number;
  model_used: string;
  is_anomaly: boolean;
}

interface RiskResponse {
  district_name: string;
  state: string;
  scores: RiskScore[];
  computed_at: string;
}

export function RiskPanel({ districtId, diseases = "dengue,malaria" }: { districtId: string; diseases?: string }) {
  const { data, error, isLoading } = useSWR<RiskResponse>(
    `/api/v1/risk/district/${districtId}?diseases=${diseases}`,
    fetcher,
    { refreshInterval: 60000 }
  );

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-48 bg-gray-100 rounded-xl"></div>
        ))}
      </div>
    );
  }

  if (error || !data) {
    return <div className="p-6 bg-red-50 text-red-600 rounded-xl">Failed to load risk intelligence. Please check if the backend is running.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">Epidemiological Risk</h2>
          <p className="text-sm text-gray-500">Live forecasting for {data.district_name}, {data.state}</p>
        </div>
        <div className="text-xs text-gray-400">
          Computed: {new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {data.scores.map((score, idx) => (
          <RiskCard key={score.disease} score={score} delay={idx * 0.1} />
        ))}
      </div>
    </div>
  );
}

function RiskCard({ score, delay }: { score: RiskScore; delay: number }) {
  const isHighRisk = score.risk_level === 'HIGH';
  const increase = score.predicted_cases - score.baseline_cases;
  const increasePercent = Math.round((increase / score.baseline_cases) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      className={`relative overflow-hidden rounded-xl border p-6 shadow-sm transition-all ${
        isHighRisk 
          ? 'border-red-200 bg-red-50/30 shadow-red-100/50' 
          : 'border-gray-200 bg-white'
      }`}
    >
      {/* Background Pulse for High Risk */}
      {isHighRisk && (
        <motion.div 
          animate={{ scale: [1, 1.05, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute -top-10 -right-10 w-32 h-32 bg-red-500/10 rounded-full blur-2xl pointer-events-none"
        />
      )}

      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg ${isHighRisk ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'}`}>
            <Activity size={18} />
          </div>
          <h3 className="font-semibold text-gray-900 capitalize">{score.disease.replace('_', ' ')}</h3>
        </div>
        <span className={`text-xs font-bold px-2 py-1 rounded-full ${
          isHighRisk ? 'bg-red-100 text-red-700' : 
          score.risk_level === 'MEDIUM' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
        }`}>
          {score.risk_level}
        </span>
      </div>

      <div className="flex items-end gap-3 mb-4">
        <div className="text-4xl font-bold tracking-tight text-gray-900">
          {score.predicted_cases}
        </div>
        <div className="text-sm text-gray-500 mb-1">predicted cases</div>
      </div>

      <div className="flex items-center gap-2 text-sm">
        <div className={`flex items-center gap-1 font-medium ${increase > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
          {increase > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {Math.abs(increasePercent)}%
        </div>
        <span className="text-gray-500">vs baseline ({score.baseline_cases})</span>
      </div>

      {score.is_anomaly && (
        <div className="mt-4 flex items-center gap-2 text-xs font-medium text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-200/50">
          <AlertTriangle size={14} />
          Search/Weather Anomaly Detected
        </div>
      )}
    </motion.div>
  );
}
