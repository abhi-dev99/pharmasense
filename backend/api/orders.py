from fastapi import APIRouter

orders_router = APIRouter(prefix="/orders", tags=["orders"])

@orders_router.get("/{hospital_id}")
async def get_orders(hospital_id: str):
    return {"hospital_id": hospital_id, "orders": []}
