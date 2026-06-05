from fastapi import APIRouter, HTTPException
from typing import Optional
from backend.schemas import ForecastResponse, DrugOrder
from backend.db.queries.inventory import get_hospital_details

forecast_router = APIRouter(prefix="/forecast", tags=["forecast"])

@forecast_router.get("/hospital/{hospital_id}", response_model=ForecastResponse)
async def get_hospital_forecast(
    hospital_id: str,
    horizon_weeks: int = 4,
    budget_inr: Optional[float] = None
):
    hospital = get_hospital_details(hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
        
    # Stub LP Optimizer output
    orders = [
        DrugOrder(
            drug_id="drg_001",
            drug_name="Paracetamol 500mg",
            order_quantity=5000,
            order_cost_inr=15000.0,
            weeks_of_cover=8,
            urgency="HIGH",
            reason="High dengue risk in district"
        )
    ]
    
    return ForecastResponse(
        hospital_id=hospital_id,
        optimization_status="OPTIMAL",
        orders=orders,
        total_cost_inr=15000.0,
        drugs_at_risk=["Paracetamol 500mg"]
    )

from backend.schemas import LongTermForecastResponse
from backend.ml.prophet import infer_long_term

@forecast_router.get("/long-term/{district_id}", response_model=LongTermForecastResponse)
async def get_long_term_forecast(
    district_id: str,
    disease: str,
    months_ahead: int = 6
):
    result = infer_long_term(district_id, disease, months_ahead)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
        
    return LongTermForecastResponse(**result)
