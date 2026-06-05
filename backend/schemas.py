from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date, datetime

class HospitalBase(BaseModel):
    id: str
    name: str
    tier: str
    district_id: str
    bed_count: int

class DrugOrder(BaseModel):
    drug_id: str
    drug_name: str
    order_quantity: float
    order_cost_inr: float
    weeks_of_cover: float
    urgency: str  # CRITICAL / HIGH / NORMAL / DEFER
    reason: str

class ForecastRequest(BaseModel):
    hospital_id: str
    horizon_weeks: int = 4
    budget_inr: Optional[float] = None

class ForecastResponse(BaseModel):
    hospital_id: str
    optimization_status: str
    orders: List[DrugOrder]
    total_cost_inr: float
    drugs_at_risk: List[str]

class RiskScore(BaseModel):
    disease: str
    score: float
    risk_level: str
    predicted_cases: int
    baseline_cases: int  # Added to represent Prophet's independent baseline prediction
    model_used: str
    weather_score: float
    search_score: float
    epid_baseline: float
    is_anomaly: bool

class RiskResponse(BaseModel):
    district_id: str
    district_name: str
    state: str
    scores: List[RiskScore]
    computed_at: str
    cache_hit: bool

class OutbreakEvent(BaseModel):
    event_id: str
    district_id: str
    disease: str
    risk_score: float
    risk_level: str
    triggered_at: datetime
    hospitals: List[Dict]
    expires_at: datetime
