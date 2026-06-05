from fastapi import APIRouter
from typing import Dict
from pydantic import BaseModel

simulate_router = APIRouter(prefix="/simulate", tags=["simulate"])

class SimulationRequest(BaseModel):
    district_ids: list[str]
    intensity: float
    duration_weeks: int

class SimulationResponse(BaseModel):
    baseline_scores: Dict[str, float]
    simulated_scores: Dict[str, float]
    delta_scores: Dict[str, float]

@simulate_router.post("/monsoon", response_model=SimulationResponse)
async def run_monsoon_simulation(req: SimulationRequest):
    """
    Simulates a monsoon event across provided districts.
    Increases weather signals and runs prediction without saving to DB.
    """
    # Stub simulation
    baseline = {d: 0.4 for d in req.district_ids}
    simulated = {d: min(1.0, 0.4 + (req.intensity * 0.5)) for d in req.district_ids}
    delta = {d: simulated[d] - baseline[d] for d in req.district_ids}
    
    return SimulationResponse(
        baseline_scores=baseline,
        simulated_scores=simulated,
        delta_scores=delta
    )
