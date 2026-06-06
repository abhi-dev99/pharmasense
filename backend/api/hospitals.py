from fastapi import APIRouter, HTTPException
from backend.db.client import DBClient
import structlog

log = structlog.get_logger()
hospitals_router = APIRouter(prefix="/hospitals", tags=["hospitals"])

@hospitals_router.get("/{hospital_id}")
async def get_hospital(hospital_id: str):
    try:
        res = DBClient.get_supabase_a()\
            .table("hospitals")\
            .select("id, name, district_id, tier, bed_count")\
            .eq("id", hospital_id)\
            .limit(1)\
            .execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Hospital not found")
        
        hospital = res.data[0]
        
        # Get district name
        district_res = DBClient.get_supabase_a()\
            .table("districts")\
            .select("name, state")\
            .eq("id", hospital["district_id"])\
            .limit(1)\
            .execute()
        
        district_name = "Unknown"
        state = "Unknown"
        if district_res.data:
            district_name = district_res.data[0]["name"]
            state = district_res.data[0]["state"]
        
        return {
            "id": hospital["id"],
            "name": hospital["name"],
            "district_id": hospital["district_id"],
            "district_name": district_name,
            "state": state,
            "tier": hospital.get("tier"),
            "bed_count": hospital.get("bed_count"),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("api.hospitals.error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@hospitals_router.get("/{hospital_id}/inventory")
async def get_hospital_inventory_detail(hospital_id: str):
    """Returns full inventory with drug details for a hospital."""
    try:
        res = DBClient.get_supabase_a()\
            .table("inventory")\
            .select("id, stock_units, reorder_point, updated_at, drugs(id, name, generic_name, dose_mg, formulation_type, price_inr, icmr_diseases)")\
            .eq("hospital_id", hospital_id)\
            .execute()
        return {"hospital_id": hospital_id, "inventory": res.data}
    except Exception as e:
        log.error("api.hospitals.inventory.error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
