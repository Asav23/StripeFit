"""Free tier vs StripeFit Pro. The free-tier limit lives in config (FREE_ITEM_LIMIT)."""

from sqlmodel import Session, func, select

from app.config import settings
from app.errors import api_error
from app.models import Item, User

UPGRADE_NEXT_STEP = "Get StripeFit Pro (€2.99 one-off) on the Pro tab."


def get_user(session: Session) -> User:
    user = session.get(User, 1)
    if user is None:
        user = User(id=1)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def is_premium(session: Session) -> bool:
    return get_user(session).premium


def confirmed_count(session: Session) -> int:
    query = select(func.count()).select_from(Item).where(Item.confirmed == True, Item.status != "returned")  # noqa: E712
    return session.exec(query).one()


def pending_count(session: Session) -> int:
    query = select(func.count()).select_from(Item).where(Item.confirmed == False, Item.dismissed == False)  # noqa: E712
    return session.exec(query).one()


def ensure_capacity(session: Session, adding: int = 1) -> None:
    """Raise 402 upgrade_required if adding `adding` confirmed items would pass the free limit."""
    if is_premium(session):
        return
    limit = settings.FREE_ITEM_LIMIT
    if confirmed_count(session) + adding > limit:
        raise api_error(
            402,
            "upgrade_required",
            f"The free plan holds {limit} items and your wardrobe is full.",
            UPGRADE_NEXT_STEP,
        )


def require_pro(session: Session, feature: str) -> None:
    if not is_premium(session):
        raise api_error(402, "upgrade_required", f"{feature} is part of StripeFit Pro.", UPGRADE_NEXT_STEP)
