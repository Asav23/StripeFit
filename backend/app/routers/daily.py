"""The outfit of the day (today or tomorrow), planned from the calendar, weather and laundry."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.schemas import DailyResponse, DailySettings, DailySettingsOut, DayEventOut
from app.services import daily, outfit_engine
from app.services.google_calendar import DayEvent
from app.models import Outfit

router = APIRouter(prefix="/api/daily", tags=["daily"])


def _response(session: Session, day: str, outfit: Outfit, events: list[DayEvent]) -> DailyResponse:
    return DailyResponse(day=outfit.for_date or day, outfit=outfit_engine.outfit_out(session, outfit),
                         events=[DayEventOut(**e.public()) for e in events], settings=daily.settings_out(session))


@router.get("", response_model=DailyResponse)
def outfit_for_day(day: str = "today", session: Session = Depends(get_session)) -> DailyResponse:
    """`day` = today | tomorrow. Made on first request (or by the scheduler) and rebuilt if the calendar changes.
    Swap / wear / feedback use /api/outfits/{id}/… as usual."""
    outfit, events = daily.get_or_make(session, daily.resolve_day(day))
    return _response(session, day, outfit, events)


@router.post("/another", response_model=DailyResponse)
def another_option(day: str = "today", session: Session = Depends(get_session)) -> DailyResponse:
    """A different outfit for the same day, avoiding the pieces already suggested."""
    date = daily.resolve_day(day)
    outfit = daily.make(session, date, another=True)
    events, _ = daily.google_calendar.events_for(date)
    return _response(session, day, outfit, events)


@router.get("/settings", response_model=DailySettingsOut)
def get_settings(session: Session = Depends(get_session)) -> DailySettingsOut:
    return daily.settings_out(session)


@router.put("/settings", response_model=DailySettingsOut)
def put_settings(body: DailySettings, session: Session = Depends(get_session)) -> DailySettingsOut:
    return daily.update_settings(session, body)
