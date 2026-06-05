from fastapi import APIRouter

admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.post("/batch")
async def trigger_batch():
    return {"status": "Batch processing started (stub)"}
