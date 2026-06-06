from fastapi import APIRouter, HTTPException
from backend.schemas import BriefResponse
from backend.db.queries.inventory import get_hospital_details
from backend.db.client import DBClient
import structlog
import os

log = structlog.get_logger()
brief_router = APIRouter(prefix="/brief", tags=["brief"])

@brief_router.get("/hospital/{hospital_id}", response_model=BriefResponse)
async def get_hospital_brief(hospital_id: str):
    hospital = get_hospital_details(hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # ── Gather real context from Supabase ────────────────────────────────────
    district_id = hospital.get("district_id", "")
    hospital_name = hospital.get("name", "Unknown Hospital")
    bed_count = hospital.get("bed_count", 0)

    # Get district info
    try:
        d_res = DBClient.get_supabase_a().table("districts")\
            .select("name, state").eq("id", district_id).limit(1).execute()
        district_name = d_res.data[0]["name"] if d_res.data else district_id
        state = d_res.data[0]["state"] if d_res.data else ""
    except Exception:
        district_name = district_id
        state = ""

    # Get top disease risk
    try:
        epid_res = DBClient.get_supabase_a().table("epid_weekly")\
            .select("disease, cases").eq("district_id", district_id)\
            .order("cases", desc=True).limit(3).execute()
        disease_summary = [(r["disease"].replace("_", " ").title(), r["cases"]) for r in epid_res.data]
    except Exception:
        disease_summary = []

    # Get inventory status (low stock items)
    low_stock_items = []
    try:
        inv_res = DBClient.get_supabase_a().table("inventory")\
            .select("stock_units, reorder_point, drugs(name, icmr_diseases)")\
            .eq("hospital_id", hospital_id).execute()

        daily_rate = max(1, int(bed_count * 0.5))
        for row in inv_res.data:
            drug = row.get("drugs", {})
            if not drug:
                continue
            days_cover = row["stock_units"] / daily_rate if daily_rate > 0 else 999
            if days_cover < 30:
                low_stock_items.append({
                    "name": drug.get("name"),
                    "days": round(days_cover),
                    "diseases": drug.get("icmr_diseases") or []
                })
    except Exception as e:
        log.warning("brief.inventory_fetch_failed", error=str(e))

    # ── Build Gemini prompt ──────────────────────────────────────────────────
    disease_lines = "\n".join([f"- {d}: {c:,} cases" for d, c in disease_summary]) or "- No active outbreak data found."
    stock_lines = "\n".join([f"- {i['name']}: {i['days']} days remaining" for i in low_stock_items[:5]]) or "- All critical stock levels are adequate."

    prompt = f"""You are Pharmasense, an AI health supply chain analyst. 
Generate a concise executive brief (max 150 words) for a hospital administrator.
Use professional, factual language. Structure as: situation → risk → action.

Hospital: {hospital_name}
Location: {district_name}, {state}
Beds: {bed_count}

District Disease Burden (cumulative cases):
{disease_lines}

Low Inventory Alerts (< 30 days cover):
{stock_lines}

Write the brief in plain text with **bold** for key terms. Do NOT use headers or bullet points.
Start with the most critical risk, then inventory situation, then recommended actions."""

    # ── Call Gemini ──────────────────────────────────────────────────────────
    try:
        from google import genai
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_GEMINI_API_KEY not set")
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt
        )
        brief_text = response.text.strip()
    except Exception as e:
        log.warning("brief.gemini_failed", error=str(e))
        # Fallback: generate a template-based brief from real data
        top_disease = disease_summary[0][0] if disease_summary else "Dengue"
        top_cases = f"{disease_summary[0][1]:,}" if disease_summary else "N/A"
        low_drug = low_stock_items[0]["name"] if low_stock_items else None
        brief_text = (
            f"**{hospital_name}** in **{district_name}** is managing an active **{top_disease}** outbreak "
            f"with {top_cases} cumulative district cases. "
        )
        if low_drug:
            brief_text += f"**{low_drug}** has fewer than {low_stock_items[0]['days']} days of cover and requires immediate procurement. "
        brief_text += "Recommend reviewing and approving pending purchase orders for disease-relevant drugs to maintain uninterrupted supply chain coverage."

    return BriefResponse(brief_markdown=brief_text, cache_hit=False)
