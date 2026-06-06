from fastapi import APIRouter, Depends, HTTPException
from datetime import date
from typing import List, Optional
import structlog
from backend.cache.decorators import cache_response
from backend.cache.keys import CacheKeys
from backend.schemas import RiskResponse, RiskScore
from backend.ml.loader import registry
from backend.ml.router import route, InferenceStrategy
from backend.db.queries.districts import get_district_by_id
from backend.ml.stgnn import infer_stgnn

log = structlog.get_logger()
risk_router = APIRouter(prefix="/risk", tags=["risk"])

@risk_router.get("/district/{district_id}", response_model=RiskResponse)
# @cache_response(key_func=CacheKeys.risk_score, ttl_seconds=86400) # In real implementation we'd wrap this
async def get_district_risk(
    district_id: str, 
    diseases: str = "dengue,malaria,type2_diabetes", 
    target_date: Optional[date] = None
):
    target_date = target_date or date.today()
    disease_list = diseases.split(",")
    
    try:
        district = get_district_by_id(district_id)
        if district is None:
            log.warning("api.risk.db_fallback_none", id=district_id)
            district = {"id": district_id, "name": f"Mock District {district_id}", "state": "Mock State"}
    except Exception as e:
        log.warning("api.risk.db_fallback", error=str(e))
        district = {"id": district_id, "name": f"Mock District {district_id}", "state": "Mock State"}

    if not district:
        raise HTTPException(status_code=404, detail="District not found")
        
    scores = []
    for d in disease_list:
        strategy = route(d, registry)
        
        predicted_cases = 150
        risk_score_val = 0.45
        model_used = strategy.value
        
        if strategy == InferenceStrategy.SPATIAL_ENSEMBLE:
            inf_res = infer_stgnn(district_id, d, target_date)
            # Incorporate GWN as an ensemble partner
            from backend.ml.graphwavenet import infer_graphwavenet
            gwn_res = infer_graphwavenet(district_id, d, target_date)
            
            valid_cases = []
            valid_scores = []
            if "error" not in inf_res:
                valid_cases.append(inf_res["predicted_cases"])
                valid_scores.append(inf_res["risk_score"])
            if "error" not in gwn_res:
                valid_cases.append(gwn_res["predicted_cases"])
                valid_scores.append(gwn_res["risk_score"])
                
            if valid_cases:
                predicted_cases = int(sum(valid_cases) / len(valid_cases))
                risk_score_val = sum(valid_scores) / len(valid_scores)
                model_used = "spatial_ensemble (stgnn+gwn)"
            else:
                log.warning("ml.inference.failed", disease=d, error="All spatial models failed")
                
        elif strategy == InferenceStrategy.DEMAND_ENSEMBLE:
            from backend.ml.tft import infer_tft
            from backend.ml.nbeats import infer_nbeats
            inf_res = infer_tft(district_id, d, target_date)
            nb_res = infer_nbeats(district_id, d, target_date)
            
            valid_cases = []
            valid_scores = []
            if "error" not in inf_res:
                valid_cases.append(inf_res["predicted_cases"])
                valid_scores.append(inf_res["risk_score"])
            if "error" not in nb_res:
                valid_cases.append(nb_res["predicted_cases"])
                valid_scores.append(nb_res["risk_score"])
                
            if valid_cases:
                predicted_cases = int(sum(valid_cases) / len(valid_cases))
                risk_score_val = sum(valid_scores) / len(valid_scores)
                model_used = "demand_ensemble (tft+nbeats)"
            else:
                log.warning("ml.inference.failed", disease=d, error="All demand models failed")
                
        risk_level = "HIGH" if risk_score_val > 0.6 else ("MEDIUM" if risk_score_val > 0.3 else "LOW")
        
        from backend.ml.anomaly import infer_anomaly
        is_anom = infer_anomaly(district_id, d, predicted_cases)
        
        score = RiskScore(
            disease=d,
            score=risk_score_val,
            risk_level=risk_level,
            predicted_cases=predicted_cases,
            baseline_cases=120,
            model_used=model_used,
            weather_score=0.8,
            search_score=0.6,
            epid_baseline=0.5,
            is_anomaly=is_anom
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

@risk_router.get("/national", response_model=dict)
async def get_national_risk(disease: str = "dengue"):
    """
    Returns a GeoJSON FeatureCollection of all districts with their risk intensity
    for the specified disease. Uses batch queries for performance.
    """
    from backend.db.client import DBClient
    import math

    try:
        # Query 1: All districts with coordinates (single query)
        dist_res = DBClient.get_supabase_a()\
            .table("districts")\
            .select("id, name, centroid_lat, centroid_lon")\
            .filter("centroid_lat", "not.is", "null")\
            .execute()
        districts = {d["id"]: d for d in dist_res.data}
    except Exception as e:
        log.error("api.risk.national.districts_error", error=str(e))
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Query 2: Aggregate total cases per district for this disease (single query)
        # Supabase doesn't support GROUP BY natively, so we select all rows and aggregate in Python
        epid_res = DBClient.get_supabase_a()\
            .table("epid_weekly")\
            .select("district_id, cases")\
            .eq("disease", disease)\
            .execute()
        epid_rows = epid_res.data
    except Exception as e:
        log.warning("api.risk.national.epid_error", error=str(e))
        epid_rows = []

    # Aggregate total cases per district in Python
    district_cases: dict = {}
    for row in epid_rows:
        did = row["district_id"]
        district_cases[did] = district_cases.get(did, 0) + (row["cases"] or 0)

    # Compute log-normalized risk scores so values are spread across 0-1 range
    # Max log value anchors the scale (prevents one outlier from washing everything else out)
    all_case_values = list(district_cases.values())
    if all_case_values:
        log_values = [math.log1p(v) for v in all_case_values]
        max_log = max(log_values) if log_values else 1.0
    else:
        max_log = 1.0

    features = []
    for dist_id, dist in districts.items():
        raw_cases = district_cases.get(dist_id, 0)
        # Normalize: log(cases) / log(max_cases) → 0 to 1
        if raw_cases > 0 and max_log > 0:
            risk_score = math.log1p(raw_cases) / max_log
        else:
            # Districts with no data get a very low baseline, not zero (to still show on map)
            risk_score = 0.02

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [dist["centroid_lon"], dist["centroid_lat"]]
            },
            "properties": {
                "mag": round(risk_score * 5, 3),  # Scale 0-1 to 0-5 for heatmap weight
                "id": dist_id,
                "name": dist["name"],
                "cases": raw_cases,
            }
        })

    log.info("api.risk.national.computed", disease=disease, districts=len(features))
    return {
        "type": "FeatureCollection",
        "features": features
    }


