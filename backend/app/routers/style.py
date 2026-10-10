"""The user's style: what they tell us, and what we've learned from thumbs, swaps and worn outfits."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.schemas import StylePreferences
from app.services import rules, style_profile
from app.services.limits import get_user

router = APIRouter(prefix="/api/style", tags=["style"])


@router.get("/profile")
def profile(occasion: str = "casual", session: Session = Depends(get_session)) -> dict[str, Any]:
    """Stated preferences + learned taste for one occasion. Item affinity scores stay server-side."""
    occasion = occasion if occasion in rules.OCCASIONS else "other"
    built = style_profile.build(session, occasion)
    return {"occasion": occasion, "stated": built["stated"], "learned": built["learned"],
            "liked_outfits": built["liked_outfits_for_this_occasion"], "signals": built["signal_count"]}


@router.put("/preferences")
def set_preferences(body: StylePreferences, session: Session = Depends(get_session)) -> dict[str, Any]:
    user = get_user(session)
    user.favourite_colours, user.avoid_colours = body.favourite_colours, body.avoid_colours
    user.style_notes = body.style_notes
    session.add(user)
    session.commit()
    return body.model_dump()
