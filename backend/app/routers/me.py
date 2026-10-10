"""The single demo user's plan and counts."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.config import settings
from app.db import get_session
from app.models import Purchase
from app.schemas import MeOut, PurchaseOut
from app.services.limits import confirmed_count, get_user, pending_count

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me", response_model=MeOut)
def me(session: Session = Depends(get_session)) -> MeOut:
    user = get_user(session)
    purchase = session.exec(select(Purchase).order_by(col(Purchase.created_at).desc())).first()
    return MeOut(
        premium=user.premium,
        premium_since=user.premium_since,
        confirmed_item_count=confirmed_count(session),
        pending_count=pending_count(session),
        item_limit=None if user.premium else settings.FREE_ITEM_LIMIT,
        mock_ai=settings.USE_MOCK_AI,
        stripe_configured=settings.stripe_configured,
        gmail_configured=settings.gmail_configured,
        latest_purchase=PurchaseOut.model_validate(purchase.model_dump()) if purchase else None,
    )
