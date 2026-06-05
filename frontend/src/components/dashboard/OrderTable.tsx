"use client";

import useSWR from 'swr';
import { motion } from 'framer-motion';
import { PackageOpen, AlertCircle, ShoppingCart } from 'lucide-react';

const fetcher = (url: string) => fetch(url).then(res => res.json());

interface DrugOrder {
  drug_id: string;
  drug_name: string;
  order_quantity: number;
  order_cost_inr: number;
  weeks_of_cover: number;
  urgency: 'HIGH' | 'MEDIUM' | 'LOW';
  reason: string;
}

interface ForecastResponse {
  hospital_id: string;
  optimization_status: string;
  orders: DrugOrder[];
  total_cost_inr: number;
  drugs_at_risk: string[];
}

export function OrderTable({ hospitalId }: { hospitalId: string }) {
  const { data, error, isLoading } = useSWR<ForecastResponse>(
    `/api/v1/forecast/hospital/${hospitalId}`,
    fetcher
  );

  if (isLoading) {
    return (
      <div className="h-64 bg-gray-50 rounded-xl animate-pulse border border-gray-100 mt-6"></div>
    );
  }

  if (error || !data) {
    return null;
  }

  return (
    <div className="mt-8">
      <div className="flex justify-between items-end mb-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-gray-900">Supply Chain Optimization</h2>
          <p className="text-sm text-gray-500">LP optimizer recommendations based on risk forecasts.</p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">Required Budget</div>
          <div className="text-2xl font-bold text-[#111111]">
            ₹{data.total_cost_inr.toLocaleString('en-IN')}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 text-gray-600 font-medium border-b border-gray-200">
            <tr>
              <th className="px-4 py-3">Drug/Resource</th>
              <th className="px-4 py-3">Quantity</th>
              <th className="px-4 py-3">Cover</th>
              <th className="px-4 py-3">Est. Cost</th>
              <th className="px-4 py-3">Urgency</th>
              <th className="px-4 py-3">Reasoning</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {data.orders.map((order, idx) => (
              <motion.tr 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.1 }}
                key={order.drug_id} 
                className="hover:bg-gray-50/50 transition-colors"
              >
                <td className="px-4 py-4 font-medium text-gray-900">
                  <div className="flex items-center gap-2">
                    <PackageOpen size={16} className="text-gray-400" />
                    {order.drug_name}
                  </div>
                </td>
                <td className="px-4 py-4 text-gray-600">{order.order_quantity.toLocaleString()} units</td>
                <td className="px-4 py-4 text-gray-600">{order.weeks_of_cover} weeks</td>
                <td className="px-4 py-4 text-gray-900 font-medium">₹{order.order_cost_inr.toLocaleString('en-IN')}</td>
                <td className="px-4 py-4">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
                    order.urgency === 'HIGH' ? 'bg-red-100 text-red-700' : 
                    order.urgency === 'MEDIUM' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-700'
                  }`}>
                    {order.urgency === 'HIGH' && <AlertCircle size={12} />}
                    {order.urgency}
                  </span>
                </td>
                <td className="px-4 py-4 text-gray-500 max-w-[200px] truncate" title={order.reason}>
                  {order.reason}
                </td>
                <td className="px-4 py-4 text-right">
                  <button className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium bg-[#111111] text-white rounded-lg hover:bg-gray-800 transition-colors">
                    <ShoppingCart size={14} /> Approve
                  </button>
                </td>
              </motion.tr>
            ))}
            
            {data.orders.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                  No critical orders required. Inventory is optimal.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
