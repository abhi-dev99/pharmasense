export type Role = 'pharmacist' | 'district_officer';

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  facility_id?: string; // For pharmacist
  district?: string;    // For district_officer
}

export type RiskLevel = 'SAFE' | 'WATCH' | 'CRITICAL';

export interface Hospital {
  id: string;
  name: string;
  district: string;
  state: string;
  lat: number;
  lng: number;
  type: string;
  capacity: number;
}

export interface Drug {
  id: string;
  name: string;
  generic_name: string;
  formulation: 'Tablet' | 'Injection' | 'IV Bag' | 'Sachet' | 'Syrup';
  unit_price: number;
}

export interface InventoryItem {
  id: string;
  hospital_id: string;
  drug_id: string;
  drug: Drug;
  stock_on_hand: number;
  predicted_demand_14d: number;
  days_cover: number;
  status: RiskLevel;
  last_restocked: string;
}

export interface PurchaseOrder {
  id: string;
  hospital_id: string;
  drug_id: string;
  drug: Drug;
  quantity: number;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  trigger: 'AI' | 'MANUAL';
  ai_justification?: string;
  created_at: string;
  approved_at?: string;
  approved_by?: string;
}

export interface RiskScore {
  district: string;
  score: number; // 0-100
  level: RiskLevel | 'HIGH' | 'MODERATE' | 'LOW';
  top_disease: string;
  days_to_peak?: number;
}

export interface SignalTimelinePoint {
  date: string;
  rain_mm: number;
  search_index: number;
  predicted_cases: number;
  is_forecast: boolean;
}

export interface HospitalBrief {
  hospital_id: string;
  generated_at: string;
  content: string;
  cached: boolean;
}
