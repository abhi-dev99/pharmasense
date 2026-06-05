from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date

# ── Risk Models ──
class RiskScore(BaseModel):
    disease: str
    score: float
    risk_level: str
    predicted_cases: int
    baseline_cases: int = 0
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

# ── Forecast Models ──
class DrugOrder(BaseModel):
    drug_id: str
    drug_name: str
    order_quantity: float
    order_cost_inr: float
    weeks_of_cover: float
    urgency: str
    reason: str

class ForecastResponse(BaseModel):
    hospital_id: str
    optimization_status: str
    orders: List[DrugOrder]
    total_cost_inr: float
    drugs_at_risk: List[str]

# ── Brief Models ──
class BriefResponse(BaseModel):
    brief_markdown: str
    cache_hit: bool

# ── Long Term Prophet Models ──
class MonthlyForecast(BaseModel):
    month: str
    predicted_demand: int
    lower_bound: int
    upper_bound: int

class LongTermForecastResponse(BaseModel):
    district_id: str
    disease: str
    months_ahead: int
    total_projected_cases: int
    peak_month: str
    forecast_timeline: List[MonthlyForecast]
