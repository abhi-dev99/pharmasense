from fastapi import APIRouter

signals_router = APIRouter(prefix="/signals", tags=["signals"])

@signals_router.get("/{district_id}/timeline")
async def get_timeline(district_id: str, days: int = 7):
    return {"district_id": district_id, "points": []}
