"""The casual fit of the day, and its morning-notification settings."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.schemas import DailyResponse, DailySettings, DailySettingsOut
from app.services import daily, outfit_engine

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("", response_model=DailyResponse)
def todays_fit(session: Session = Depends(get_session)) -> DailyResponse:
    """Today's casual outfit (made on first request of the day). Swap/wear/feedback use /api/outfits/{id}/…"""
    outfit = daily.get_or_make(session)
    return DailyResponse(outfit=outfit_engine.outfit_out(session, outfit), settings=daily.settings_out(session))


@router.post("/another", response_model=DailyResponse)
def another_option(session: Session = Depends(get_session)) -> DailyResponse:
    """A different casual outfit for today, avoiding the pieces already suggested."""
    outfit = daily.make(session, another=True)
    return DailyResponse(outfit=outfit_engine.outfit_out(session, outfit), settings=daily.settings_out(session))


@router.get("/settings", response_model=DailySettingsOut)
def get_settings(session: Session = Depends(get_session)) -> DailySettingsOut:
    return daily.settings_out(session)


@router.put("/settings", response_model=DailySettingsOut)
def put_settings(body: DailySettings, session: Session = Depends(get_session)) -> DailySettingsOut:
    return daily.update_settings(session, body)
