from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from typing import List, Optional
import structlog
from backend.cache.decorators import cache_response
from backend.cache.keys import RedisKeys
from backend.schemas import RiskResponse, RiskScore
from backend.ml.loader import registry
from backend.ml.router import route, InferenceStrategy
from backend.db.queries.districts import get_district_by_id

log = structlog.get_logger()
risk_router = APIRouter(prefix="/risk", tags=["risk"])

@risk_router.get("/district/{district_id}", response_model=RiskResponse)
# @cache_response(key_func=RedisKeys.risk_score, ttl_seconds=86400) # In real implementation we'd wrap this
async def get_district_risk(
    district_id: str, 
    diseases: str = "dengue,malaria,type2_diabetes", 
    target_date: Optional[date] = None
):
    target_date = target_date or date.today()
    disease_list = diseases.split(",")
    
    district = get_district_by_id(district_id)
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
        
    scores = []
    for d in disease_list:
        strategy = route(d, registry)
        
        # Stub the ML inference execution based on the router
        # In a full implementation, we would call the wrapper for the selected strategy
        score = RiskScore(
            disease=d,
            score=0.75 if d == 'dengue' else 0.45,
            risk_level="HIGH" if d == 'dengue' else "LOW",
            predicted_cases=500 if d == 'dengue' else 150,
            baseline_cases=400 if d == 'dengue' else 120,
            model_used=strategy.value,
            weather_score=0.8,
            search_score=0.6,
            epid_baseline=0.5,
            is_anomaly=False
        )
        scores.append(score)
        
    return RiskResponse(
        district_id=district_id,
        district_name=district.get("name", "Unknown"),
        state=district.get("state", "Unknown"),
        scores=scores,
        computed_at=target_date.isoformat(),
        cache_hit=False
    )
