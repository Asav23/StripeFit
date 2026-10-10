"""Browser notifications via Web Push (VAPID). No third-party account needed.

The browser gives us a subscription (an https endpoint run by Google/Mozilla/Apple plus two keys);
we sign each message with our VAPID key from backend/.env (made by scripts/make_vapid_keys.py).
Expired subscriptions (404/410) are removed automatically.
"""

import json
import logging
from typing import Optional

from pywebpush import WebPushException, webpush
from sqlmodel import Session, select

from app.config import settings
from app.models import PushSubscription
from app.schemas import PushSubscriptionIn

log = logging.getLogger("stripefit.push")

PUSH_TTL_SECONDS = 6 * 60 * 60  # a morning outfit is useless by the evening
PUSH_TIMEOUT_SECONDS = 10
GONE_STATUSES = {404, 410}


def configured() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def subscribe(session: Session, body: PushSubscriptionIn, user_id: int = 1) -> int:
    existing = session.exec(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)).first()
    if existing:
        existing.p256dh, existing.auth = body.keys["p256dh"], body.keys["auth"]
        session.add(existing)
    else:
        session.add(PushSubscription(user_id=user_id, endpoint=body.endpoint, p256dh=body.keys["p256dh"],
                                     auth=body.keys["auth"]))
    session.commit()
    return count(session, user_id)


def unsubscribe(session: Session, endpoint: str, user_id: int = 1) -> int:
    for sub in session.exec(select(PushSubscription).where(PushSubscription.endpoint == endpoint)).all():
        session.delete(sub)
    session.commit()
    return count(session, user_id)


def count(session: Session, user_id: int = 1) -> int:
    return len(session.exec(select(PushSubscription).where(PushSubscription.user_id == user_id)).all())


def send_all(session: Session, title: str, body: str, url: str = "/today", user_id: int = 1) -> tuple[int, int]:
    """Send to every subscribed browser. Returns (sent, removed). Never raises."""
    if not configured():
        return 0, 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent = removed = 0
    for sub in session.exec(select(PushSubscription).where(PushSubscription.user_id == user_id)).all():
        status = _send_one(sub, payload)
        if status is None:
            sent += 1
        elif status in GONE_STATUSES:
            session.delete(sub)
            removed += 1
    session.commit()
    return sent, removed


def _send_one(sub: PushSubscription, payload: str) -> Optional[int]:
    """None on success, else the HTTP status (0 if there was no response)."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=PUSH_TTL_SECONDS,
            timeout=PUSH_TIMEOUT_SECONDS,
        )
        return None
    except WebPushException as exc:
        status = exc.response.status_code if exc.response is not None else 0
        log.warning("Push to %s… failed (%s)", sub.endpoint[:40], status)
        return status
    except Exception as exc:  # noqa: BLE001 - a bad subscription must never break the daily job
        log.warning("Push to %s… failed: %s", sub.endpoint[:40], type(exc).__name__)
        return 0
