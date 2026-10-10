"""Browser push subscriptions for the morning casual-fit notification."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.errors import api_error
from app.schemas import PushSubscriptionIn, PushUnsubscribeIn
from app.services import daily, push

router = APIRouter(prefix="/api/push", tags=["push"])


def _require_configured() -> None:
    if not push.configured():
        raise api_error(503, "push_not_configured", "Notifications aren't set up on the server yet.",
                        "Run `python scripts/make_vapid_keys.py` in backend/ and restart the API.")


@router.get("/config")
def config() -> dict[str, Any]:
    """The public VAPID key the browser needs to subscribe (it isn't secret)."""
    return {"configured": push.configured(), "public_key": settings.VAPID_PUBLIC_KEY or None}


@router.post("/subscribe")
def subscribe(body: PushSubscriptionIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    _require_configured()
    return {"subscribed": True, "subscriptions": push.subscribe(session, body)}


@router.post("/unsubscribe")
def unsubscribe(body: PushUnsubscribeIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    return {"subscribed": False, "subscriptions": push.unsubscribe(session, body.endpoint)}


@router.post("/test")
def send_test(session: Session = Depends(get_session)) -> dict[str, int]:
    """Send tomorrow's outfit (the night-before notification) to every subscribed browser right now."""
    _require_configured()
    if push.count(session) == 0:
        raise api_error(409, "no_subscriptions", "No browser is subscribed to notifications yet.",
                        "Turn on outfit notifications first.")
    sent, removed = daily.notify(session, daily.resolve_day("tomorrow"), daily.EVENING_TITLE)
    if sent == 0:
        raise api_error(502, "push_failed", "The notification couldn't be delivered.",
                        "Turn notifications off and on again in this browser.")
    return {"sent": sent, "removed": removed}
