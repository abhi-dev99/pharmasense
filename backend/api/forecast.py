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

    from backend.db.client import DBClient
    import structlog
    log = structlog.get_logger()

    bed_count   = hospital.get("bed_count", 200) or 200
    district_id = hospital.get("district_id", "")

    # ── Determine top active disease in this district ──────────────────────────
    active_diseases: set = {"dengue"}           # always include dengue as baseline
    try:
        epid_res = DBClient.get_supabase_a()\
            .table("epid_weekly")\
            .select("disease, cases")\
            .eq("district_id", district_id)\
            .order("cases", desc=True)\
            .limit(5)\
            .execute()
        for row in (epid_res.data or []):
            if row.get("disease"):
                active_diseases.add(row["disease"].lower())
    except Exception:
        pass

    log.info("forecast.active_diseases", diseases=list(active_diseases))

    # ── Fetch inventory with drug details ─────────────────────────────────────
    try:
        res = DBClient.get_supabase_a()\
            .table("inventory")\
            .select("stock_units, reorder_point, updated_at, drugs(id, name, price_inr, icmr_diseases)")\
            .eq("hospital_id", hospital_id)\
            .execute()
        inv_rows = res.data
    except Exception as e:
        log.error("api.forecast.inventory_fetch_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Could not fetch inventory data")

    # ── Realistic daily consumption estimate ──────────────────────────────────
    # A district pharmacy dispenses roughly 1–2% of stock per day across all drugs.
    # For a 2600-bed hospital, a typical drug sees ~20–30 units/day consumption.
    # Formula: bed_count × 0.01 ≈ 26/day for Rajiv Gandhi (2600 beds)
    base_daily_rate = max(5, int(bed_count * 0.01))   # ≈26 for RGH

    orders      = []
    total_cost  = 0.0

    for row in inv_rows:
        drug = row.get("drugs", {})
        if not drug:
            continue

        stock       = row["stock_units"]
        reorder     = row["reorder_point"]
        drug_diseases = [d.lower() for d in (drug.get("icmr_diseases") or [])]

        # Disease-relevant drugs see ~50% higher consumption during outbreaks
        is_outbreak_drug = bool(active_diseases & set(drug_diseases))
        daily_rate  = int(base_daily_rate * 1.5) if is_outbreak_drug else base_daily_rate

        days_of_cover = (stock / daily_rate) if daily_rate > 0 else 999

        # Ordering threshold: 90 days for outbreak drugs, 45 days for others
        cover_threshold = 90 if is_outbreak_drug else 45
        if days_of_cover > cover_threshold:
            continue

        # Urgency tiers (recalibrated for realistic stock levels)
        if days_of_cover < 14:
            urgency = "HIGH"
        elif days_of_cover < 45:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        # Order quantity: replenish to 60 days of cover (not 90 — keeps costs sane)
        target_stock = daily_rate * 60
        order_qty    = max(1, target_stock - stock)

        price = float(drug.get("price_inr") or 50.0)
        cost  = round(price * order_qty, 2)

        disease_label = ", ".join(drug_diseases[:3]) if drug_diseases else "general"

        orders.append(DrugOrder(
            drug_id=drug["id"],
            drug_name=drug["name"],
            order_quantity=order_qty,
            order_cost_inr=cost,
            weeks_of_cover=horizon_weeks,
            urgency=urgency,
            reason=(
                f"{round(days_of_cover)}d cover left"
                + (f" · Active outbreak drug ({disease_label})" if is_outbreak_drug else f" · {disease_label}")
                + f" · Replenish to 60d"
            )
        ))
        total_cost += cost

    # ── Sort: urgency first, then highest cost ─────────────────────────────────
    urgency_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    orders.sort(key=lambda x: (urgency_order.get(x.urgency, 3), -x.order_cost_inr))

    # ── Cap at 8 most critical, then apply budget cap of ₹15L ─────────────────
    orders     = orders[:8]
    total_cost = sum(o.order_cost_inr for o in orders)

    # Hard cap: if total > ₹15L, scale down quantities proportionally
    MAX_BUDGET_INR = 1_500_000   # ₹15 lakhs = realistic quarterly procurement
    if total_cost > MAX_BUDGET_INR and orders:
        scale = MAX_BUDGET_INR / total_cost
        for o in orders:
            unit_price       = o.order_cost_inr / max(1, o.order_quantity)
            o.order_quantity = max(1, int(o.order_quantity * scale))
            o.order_cost_inr = round(o.order_quantity * unit_price, 2)
        total_cost = sum(o.order_cost_inr for o in orders)

    drugs_at_risk = [o.drug_name for o in orders if o.urgency == "HIGH"]

    return ForecastResponse(
        hospital_id=hospital_id,
        optimization_status="OPTIMAL" if orders else "NO_ACTION_REQUIRED",
        orders=orders,
        total_cost_inr=round(total_cost, 2),
        drugs_at_risk=drugs_at_risk
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
