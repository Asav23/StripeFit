"""StripeFit Pro: a one-time €2.99 purchase via Stripe Checkout (test mode only).

Pro is only ever activated from a *verified* Stripe confirmation: a signed webhook, or a
Checkout Session we retrieved from Stripe ourselves with payment_status == "paid".
Activation is idempotent on the Checkout Session ID.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import stripe
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.config import settings
from app.errors import api_error
from app.models import Purchase, User, utcnow

log = logging.getLogger("stripefit.stripe")

PRODUCT_NAME = "StripeFit Pro"
PRODUCT_METADATA = "stripefit_pro"
PRICE_LOOKUP_KEY = "stripefit_pro_eur_299"
PRICE_CENTS = 299
CURRENCY = "eur"
USER_REF = "1"  # single demo user


def _client() -> stripe.StripeClient:
    if not settings.stripe_configured:
        raise api_error(503, "stripe_not_configured", "Payments aren't set up yet (no Stripe test key).",
                        "Add STRIPE_SECRET_KEY (sk_test_...) to backend/.env and restart the API.")
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def _line_item() -> dict[str, Any]:
    if settings.STRIPE_PRICE_ID:
        return {"price": settings.STRIPE_PRICE_ID, "quantity": 1}
    # No price created yet (scripts/stripe_setup.py not run): an inline one-time price still works.
    return {
        "price_data": {"currency": CURRENCY, "unit_amount": PRICE_CENTS, "product_data": {"name": PRODUCT_NAME}},
        "quantity": 1,
    }


def create_checkout_session() -> str:
    try:
        session = _client().v1.checkout.sessions.create(params={
            "mode": "payment",
            "line_items": [_line_item()],  # type: ignore[list-item]
            "success_url": f"{settings.FRONTEND_URL}/pro/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/pro",
            "client_reference_id": USER_REF,
            "metadata": {"product": PRODUCT_METADATA},
        })
    except stripe.StripeError as exc:
        log.warning("Checkout session failed: %s", exc)
        raise api_error(502, "stripe_error", "We couldn't start checkout with Stripe.", "Try again in a moment.")
    if not session.url:
        raise api_error(502, "stripe_error", "Stripe didn't return a checkout link.", "Try again in a moment.")
    return session.url


def is_paid_pro_session(data: dict[str, Any]) -> bool:
    return (
        data.get("payment_status") == "paid"
        and (data.get("metadata") or {}).get("product") == PRODUCT_METADATA
        and data.get("client_reference_id") == USER_REF
    )


def activate_pro(session: Session, data: dict[str, Any]) -> Purchase:
    """Idempotent: one Purchase per Checkout Session ID, premium switched on once."""
    session_id = data["id"]
    purchase = session.exec(select(Purchase).where(Purchase.stripe_session_id == session_id)).first()
    if purchase is None:
        created = data.get("created")
        purchase = Purchase(
            stripe_session_id=session_id,
            amount_total=data.get("amount_total"),
            currency=data.get("currency"),
            status="paid",
            created_at=datetime.fromtimestamp(created, timezone.utc) if created else utcnow(),
        )
        session.add(purchase)
        try:
            session.commit()
        except IntegrityError:  # webhook and success-page poll raced; the other one won
            session.rollback()
            purchase = session.exec(select(Purchase).where(Purchase.stripe_session_id == session_id)).one()
        else:
            log.info("Recorded purchase for session %s", session_id)

    user = session.get(User, 1) or User(id=1)
    if not user.premium:
        user.premium = True
        user.premium_since = utcnow()
        session.add(user)
        session.commit()
    session.refresh(purchase)
    return purchase


def retrieve_session(session_id: str) -> dict[str, Any]:
    try:
        return _client().v1.checkout.sessions.retrieve(session_id).to_dict()
    except stripe.InvalidRequestError:
        raise api_error(404, "session_not_found", "We couldn't find that checkout.", "Start checkout again from the Pro tab.")
    except stripe.StripeError as exc:
        log.warning("Session retrieve failed: %s", exc)
        raise api_error(502, "stripe_error", "Couldn't reach Stripe to confirm your payment.", "Refresh this page in a moment.")


def parse_webhook(payload: bytes, signature: str | None) -> dict[str, Any]:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise api_error(503, "webhook_not_configured", "Webhook secret not set.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise api_error(400, "bad_signature", "Invalid webhook signature.")
    return event.to_dict()
