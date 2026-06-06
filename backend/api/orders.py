from fastapi import APIRouter, HTTPException, Request, Response
from typing import Optional, List
from pydantic import BaseModel
from backend.db.client import DBClient
from backend.db.queries.inventory import get_hospital_details
import structlog
import os
import uuid
from datetime import datetime

log = structlog.get_logger()
orders_router = APIRouter(prefix="/orders", tags=["orders"])

# ─── Schemas ─────────────────────────────────────────────────────────────────
class CreateOrderRequest(BaseModel):
    hospital_id: str
    drug_id: str
    drug_name: str
    quantity: int
    unit_cost_inr: float
    reason: str
    mode: str = "manual"           # "autonomous" | "oversight" | "manual"
    phone_number: Optional[str] = None  # for oversight mode WhatsApp

class ApproveOrderRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None

# ─── In-memory orders store (keyed list + SID index) ─────────────────────────
_orders_store: List[dict] = []
_sid_to_order_id: dict = {}        # twilio_sid → order_id  (for reaction lookup)

# ─── Helper: Send WhatsApp via Twilio — returns SID or None ──────────────────
def send_whatsapp_alert(to_number: str, message: str) -> Optional[str]:
    try:
        from twilio.rest import Client
        from dotenv import load_dotenv
        load_dotenv()

        account_sid   = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token    = os.getenv("TWILIO_AUTH_TOKEN")
        from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

        if not account_sid or not auth_token:
            log.warning("twilio.not_configured")
            return None

        # Normalise 'from'
        if not from_whatsapp.startswith("whatsapp:"):
            from_whatsapp = f"whatsapp:{from_whatsapp}"

        # Normalise 'to' — strip any existing prefix, ensure + prefix
        clean_to = to_number.replace("whatsapp:", "").strip()
        if not clean_to.startswith("+"):
            clean_to = f"+{clean_to}"
        to_whatsapp = f"whatsapp:{clean_to}"

        client = Client(account_sid, auth_token)
        msg = client.messages.create(body=message, from_=from_whatsapp, to=to_whatsapp)
        log.info("twilio.whatsapp_sent", to=to_whatsapp, sid=msg.sid)
        return msg.sid
    except Exception as e:
        log.error("twilio.whatsapp_failed", error=str(e))
        return None


# ─── Routes ──────────────────────────────────────────────────────────────────

@orders_router.get("/hospital/{hospital_id}")
async def list_hospital_orders(hospital_id: str):
    """Returns all purchase orders for a hospital (in-memory + DB)."""
    hospital_orders = [o for o in _orders_store if o["hospital_id"] == hospital_id]
    try:
        res = DBClient.get_supabase_a()\
            .table("purchase_orders")\
            .select("*")\
            .eq("hospital_id", hospital_id)\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        db_orders = res.data or []
    except Exception:
        db_orders = []
    all_orders = db_orders + hospital_orders
    return {"hospital_id": hospital_id, "orders": all_orders, "total": len(all_orders)}


@orders_router.post("/create")
async def create_order(req: CreateOrderRequest):
    """
    Creates a purchase order in one of three modes:
    - autonomous : auto-approved and dispatched to vendor (no human step)
    - oversight  : sends WhatsApp alert, waits for APPROVE/REJECT reply or 👍 reaction
    - manual     : creates a DRAFT for pharmacist review in the dashboard
    """
    order_id  = str(uuid.uuid4())[:8].upper()
    total_cost = req.quantity * req.unit_cost_inr
    now = datetime.now().isoformat()

    if req.mode == "autonomous":
        status    = "AUTO_APPROVED"
        auto_note = "Order auto-approved and dispatched to vendor."
    elif req.mode == "oversight":
        status    = "PENDING_APPROVAL"
        auto_note = "WhatsApp notification sent. Awaiting your reply (APPROVE/REJECT) or thumbs-up reaction."
    else:
        status    = "DRAFT"
        auto_note = "Draft order created. Review and approve manually."

    order = {
        "id":            order_id,
        "hospital_id":   req.hospital_id,
        "drug_id":       req.drug_id,
        "drug_name":     req.drug_name,
        "quantity":      req.quantity,
        "unit_cost_inr": req.unit_cost_inr,
        "total_cost_inr":round(total_cost, 2),
        "reason":        req.reason,
        "mode":          req.mode,
        "status":        status,
        "note":          auto_note,
        "created_at":    now,
        "twilio_sid":    None,
    }
    _orders_store.append(order)

    # Send WhatsApp for oversight mode and record the SID for reaction matching
    if req.mode == "oversight" and req.phone_number:
        hospital = get_hospital_details(req.hospital_id)
        h_name   = hospital.get("name", "Your Hospital") if hospital else "Your Hospital"
        message  = (
            f"🏥 *Pharmasense PO Alert — {h_name}*\n\n"
            f"📦 *Drug*: {req.drug_name}\n"
            f"🔢 *Qty*: {req.quantity:,} units\n"
            f"💰 *Cost*: ₹{total_cost:,.0f}\n"
            f"📋 *Reason*: {req.reason}\n\n"
            f"Order ID: *#{order_id}*\n\n"
            f"👉 *Long-press this message → Reply → type:*\n"
            f"   ✅ *approve* — to approve\n"
            f"   ❌ *reject*  — to reject\n\n"
            f"_(No order ID needed — just reply directly to this message)_"
        )
        sid = send_whatsapp_alert(req.phone_number, message)
        if sid:
            order["twilio_sid"] = sid
            _sid_to_order_id[sid] = order_id

    return {"success": True, "order_id": order_id, "status": status, "message": auto_note, "order": order}


@orders_router.patch("/{order_id}/approve")
async def approve_order(order_id: str, req: ApproveOrderRequest):
    """Approve or reject a pending order via dashboard UI."""
    order = next((o for o in _orders_store if o["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order["status"]      = "APPROVED" if req.approved else "REJECTED"
    order["note"]        = req.notes or ("Approved by pharmacist." if req.approved else "Rejected by pharmacist.")
    order["actioned_at"] = datetime.now().isoformat()
    return {"success": True, "order_id": order_id, "status": order["status"]}


# ─── Twilio Webhook — handles replies AND thumbs-up reactions ────────────────
@orders_router.post("/webhook/twilio")
async def twilio_webhook(request: Request):
    """
    Twilio POSTs here when a WhatsApp user:
      - Replies with text  -> parsed for APPROVE <ID> / REJECT <ID>
      - Reacts with emoji  -> thumbsup / tick = approve
    Configure this URL in Twilio console:
      https://<your-ngrok-url>/api/v1/orders/webhook/twilio
    """
    # Always return valid TwiML — even if processing fails — so Twilio doesn't retry
    TWIML_OK = Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml"
    )
    try:
        form                = await request.form()
        body                = (form.get("Body") or "").strip().upper()
        reaction_emoji      = (form.get("ReactionEmoji") or "").strip()
        reaction_sid        = (form.get("ReactionMessageSid") or "").strip()
        original_replied_sid = (form.get("OriginalRepliedMessageSid") or "").strip()

        # Log safely — encode emoji to avoid Windows cp1252 crash
        safe_reaction = reaction_emoji.encode("ascii", errors="replace").decode()

        # If body is empty, log ALL fields — useful for debugging reactions
        if not body and not reaction_emoji:
            all_fields = {k: str(v)[:60] for k, v in form.items()}
            log.info("twilio.webhook.unknown_event", fields=str(all_fields)[:300])
        else:
            log.info("twilio.webhook.received", body=body[:80], reaction=safe_reaction,
                     replied_to=original_replied_sid or reaction_sid or "none")

        updated_order_id = None
        APPROVE_EMOJIS   = ("\U0001f44d", "\U0001f919", "\u2705", "\U0001f44f")

        # ── Helper: resolve order_id from explicit ID or replied-message SID ──
        def resolve_order_id(explicit_id: str | None, replied_sid: str) -> str | None:
            if explicit_id:
                return explicit_id
            # User replied to the original alert message — look up by SID
            return _sid_to_order_id.get(replied_sid)

        # ── Emoji reaction → approve ───────────────────────────────────────────
        if reaction_emoji in APPROVE_EMOJIS:
            order_id = _sid_to_order_id.get(reaction_sid)
            if order_id:
                for o in _orders_store:
                    if o["id"] == order_id:
                        o["status"]      = "APPROVED"
                        o["note"]        = "Approved via WhatsApp reaction."
                        o["actioned_at"] = datetime.now().isoformat()
                        updated_order_id = order_id
                        log.info("twilio.reaction.approved", order_id=order_id)
                        break
            else:
                log.warning("twilio.reaction.no_matching_sid", reaction_sid=reaction_sid)

        # ── "APPROVE" or "APPROVE <ID>" ────────────────────────────────────────
        # Works both ways:
        #   • Long-press → Reply → type "approve"      (uses OriginalRepliedMessageSid)
        #   • Type "APPROVE XYZ123"  in any message    (uses explicit ID)
        elif body.startswith("APPROVE"):
            parts    = body.split()
            explicit = parts[1] if len(parts) > 1 else None
            order_id = resolve_order_id(explicit, original_replied_sid)
            if order_id:
                for o in _orders_store:
                    if o["id"] == order_id:
                        o["status"]      = "APPROVED"
                        o["note"]        = "Approved via WhatsApp reply."
                        o["actioned_at"] = datetime.now().isoformat()
                        updated_order_id = order_id
                        log.info("twilio.reply.approved", order_id=order_id)
                        break
            else:
                log.warning("twilio.reply.no_order_found", body=body, replied_sid=original_replied_sid)

        # ── "REJECT" or "REJECT <ID>" ──────────────────────────────────────────
        elif body.startswith("REJECT"):
            parts    = body.split()
            explicit = parts[1] if len(parts) > 1 else None
            order_id = resolve_order_id(explicit, original_replied_sid)
            if order_id:
                for o in _orders_store:
                    if o["id"] == order_id:
                        o["status"]      = "REJECTED"
                        o["note"]        = "Rejected via WhatsApp reply."
                        o["actioned_at"] = datetime.now().isoformat()
                        updated_order_id = order_id
                        log.info("twilio.reply.rejected", order_id=order_id)
                        break
            else:
                log.warning("twilio.reply.no_order_found", body=body, replied_sid=original_replied_sid)

        log.info("twilio.webhook.done", updated=updated_order_id)

    except Exception as exc:
        log.error("twilio.webhook.error", error=str(exc)[:200])

    return TWIML_OK


@orders_router.get("/webhook/status")
async def webhook_status():
    """Returns the current in-memory order store — for debugging."""
    return {
        "total_orders":  len(_orders_store),
        "sid_index_size": len(_sid_to_order_id),
        "orders": _orders_store,
    }
