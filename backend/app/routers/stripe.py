"""Stripe Checkout for StripeFit Pro (test mode)."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.db import get_session
from app.schemas import PurchaseOut
from app.services import stripe_service

router = APIRouter(prefix="/api/stripe", tags=["stripe"])
log = logging.getLogger("stripefit.stripe")


@router.post("/checkout")
def checkout() -> dict[str, str]:
    return {"url": stripe_service.create_checkout_session()}


@router.post("/webhook")
async def webhook(request: Request, session: Session = Depends(get_session)) -> dict[str, bool]:
    payload = await request.body()  # raw body: the signature is computed over the exact bytes
    event = stripe_service.parse_webhook(payload, request.headers.get("stripe-signature"))
    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        if stripe_service.is_paid_pro_session(data):
            stripe_service.activate_pro(session, data)
        else:
            log.info("Ignoring completed session %s (not a paid Pro purchase)", data.get("id"))
    return {"received": True}


@router.get("/session/{session_id}")
def session_status(session_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    """Called by the success page: confirms with Stripe directly, so Pro works even if the webhook is late."""
    data = stripe_service.retrieve_session(session_id)
    if not stripe_service.is_paid_pro_session(data):
        return {"paid": False, "payment_status": data.get("payment_status"), "purchase": None}
    purchase = stripe_service.activate_pro(session, data)
    return {"paid": True, "payment_status": "paid", "purchase": PurchaseOut.model_validate(purchase.model_dump())}
