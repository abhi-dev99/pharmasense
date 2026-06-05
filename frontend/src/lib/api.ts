import {
  District,
  Hospital,
  InventoryItem,
  PurchaseOrder,
  RiskScore,
  SignalTimelinePoint,
  HospitalBrief,
} from './types';

// For Vercel/Next.js, we'll proxy requests or use direct URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/**
 * Core fetch wrapper with standard headers and error handling
 */
async function fetchClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  // NOTE: Auth token injection will happen here via Supabase session
  
  const response = await fetch(url, { ...options, headers });
  
  if (!response.ok) {
    let errorMsg = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMsg = errorData.message || errorData.error || response.statusText;
    } catch (e) {
      errorMsg = response.statusText;
    }
    throw new ApiError(errorMsg, response.status);
  }
  
  return response.json();
}

export const api = {
  // --- Districts & Risk ---
  getDistricts: () => 
    fetchClient<RiskScore[]>('/districts'),
    
  getDistrictRisk: (districtId: string) => 
    fetchClient<RiskScore>(`/districts/${districtId}/risk`),
    
  // --- Hospitals ---
  getHospital: (hospitalId: string) => 
    fetchClient<Hospital>(`/hospitals/${hospitalId}`),
    
  getInventory: (hospitalId: string) => 
    fetchClient<InventoryItem[]>(`/hospitals/${hospitalId}/inventory`),
    
  getHospitalBrief: (hospitalId: string) => 
    fetchClient<HospitalBrief>(`/hospitals/${hospitalId}/brief`),
    
  // --- Orders ---
  getPurchaseOrders: (hospitalId?: string) => {
    const qs = hospitalId ? `?hospital_id=${hospitalId}` : '';
    return fetchClient<PurchaseOrder[]>(`/purchase-orders${qs}`);
  },
    
  approvePurchaseOrder: (orderId: string) => 
    fetchClient<PurchaseOrder>(`/purchase-orders/${orderId}/approve`, { method: 'POST' }),
    
  rejectPurchaseOrder: (orderId: string) => 
    fetchClient<PurchaseOrder>(`/purchase-orders/${orderId}/reject`, { method: 'POST' }),
    
  // --- Intelligence & Signals ---
  getSignalTimeline: (districtId: string) => 
    fetchClient<SignalTimelinePoint[]>(`/signals/timeline/${districtId}`),
    
  // --- Simulation ---
  simulateMonsoon: (params: { intensity: number; duration_weeks: number; districts: string[] }) =>
    fetchClient<{ affected_hospitals: number; new_critical_drugs: number; simulated_orders: number }>(
      '/simulate/monsoon',
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    ),
};
