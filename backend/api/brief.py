from fastapi import APIRouter, HTTPException
from backend.schemas import BriefResponse
from backend.db.queries.inventory import get_hospital_details

brief_router = APIRouter(prefix="/brief", tags=["brief"])

@brief_router.get("/hospital/{hospital_id}", response_model=BriefResponse)
async def get_hospital_brief(hospital_id: str):
    hospital = get_hospital_details(hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
        
    # Stub LLM output for now
    markdown = f"""
# Hospital Brief: {hospital.get('name', 'Unknown')}
**District Risk**: High Dengue Alert
**Inventory**: Critically low on IV Fluids and Paracetamol.
**Action Required**: Approve pending purchase orders.
"""
    
    return BriefResponse(
        brief_markdown=markdown,
        cache_hit=False
    )
