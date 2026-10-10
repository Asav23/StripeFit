"""Outfit planning, swapping, wearing and feedback."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.db import get_session
from app.errors import not_found
from app.models import Outfit
from app.schemas import FeedbackRequest, OutfitOut, PlanRequest, PlanResponse, SwapRequest
from app.services import outfit_engine

router = APIRouter(prefix="/api/outfits", tags=["outfits"])
HISTORY_LIMIT = 30


def _get(session: Session, outfit_id: int) -> Outfit:
    outfit = session.get(Outfit, outfit_id)
    if outfit is None:
        raise not_found("Outfit")
    return outfit


@router.post("/plan", response_model=PlanResponse)
def plan(body: PlanRequest, session: Session = Depends(get_session)) -> PlanResponse:
    return outfit_engine.plan_outfit(session, body.request_text)


@router.get("", response_model=list[OutfitOut])
def history(session: Session = Depends(get_session)) -> list[OutfitOut]:
    outfits = session.exec(select(Outfit).order_by(col(Outfit.created_at).desc()).limit(HISTORY_LIMIT)).all()
    return [outfit_engine.outfit_out(session, o) for o in outfits]


@router.get("/{outfit_id}", response_model=OutfitOut)
def get_outfit(outfit_id: int, session: Session = Depends(get_session)) -> OutfitOut:
    return outfit_engine.outfit_out(session, _get(session, outfit_id))


@router.post("/{outfit_id}/swap", response_model=OutfitOut)
def swap(outfit_id: int, body: SwapRequest, session: Session = Depends(get_session)) -> OutfitOut:
    outfit = outfit_engine.swap_slot(session, _get(session, outfit_id), body.slot)
    return outfit_engine.outfit_out(session, outfit)


@router.post("/{outfit_id}/wear", response_model=OutfitOut)
def wear(outfit_id: int, session: Session = Depends(get_session)) -> OutfitOut:
    outfit = outfit_engine.wear_outfit(session, _get(session, outfit_id))
    return outfit_engine.outfit_out(session, outfit)


@router.post("/{outfit_id}/feedback", response_model=OutfitOut)
def feedback(outfit_id: int, body: FeedbackRequest, session: Session = Depends(get_session)) -> OutfitOut:
    outfit = outfit_engine.set_feedback(session, _get(session, outfit_id), body.feedback)
    return outfit_engine.outfit_out(session, outfit)
