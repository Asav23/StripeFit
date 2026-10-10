"""Google Calendar connection (read-only), used to plan tomorrow's outfit around your day."""

import logging
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.errors import api_error
from app.schemas import DayEventOut
from app.services import daily, google_calendar, ical_calendar

router = APIRouter(prefix="/api/calendar", tags=["calendar"])
log = logging.getLogger("stripefit.calendar")


def _require_configured() -> None:
    if not settings.gmail_configured:  # the same Google OAuth client serves Gmail and Calendar
        raise api_error(503, "calendar_not_configured", "Google Calendar isn't set up yet.",
                        "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env and restart the API.")


@router.get("/status")
def status() -> dict[str, Any]:
    """configured/connected = the Google sign-in; link = a private iCal link is saved; source = what's used."""
    return {"configured": settings.gmail_configured, "connected": google_calendar.connected(),
            "link": ical_calendar.connected(), "demo": google_calendar.DEMO_EVENTS is not None,
            "source": google_calendar.source()}


class CalendarLink(BaseModel):
    url: str = Field(min_length=10, max_length=600)


@router.put("/link")
def save_link(body: CalendarLink) -> dict[str, Any]:
    """Use a private iCal link instead of the Google sign-in. The link is checked before it's saved."""
    try:
        count = ical_calendar.save_link(body.url)
    except ical_calendar.BadLink as exc:
        raise api_error(422, "invalid_calendar_link", str(exc), "Copy the secret iCal address again and paste it here.")
    return {"link": True, "events": count}


@router.delete("/link")
def remove_link() -> dict[str, bool]:
    ical_calendar.remove_link()
    return {"link": False}


@router.get("/auth-url")
def auth_url() -> dict[str, str]:
    _require_configured()
    return {"url": google_calendar.auth_url()}


@router.get("/callback")
def callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None) -> RedirectResponse:
    """Google redirects here after consent. We always send the browser back to the app."""
    target = f"{settings.FRONTEND_URL}/today?calendar="
    if error or not code or not state:
        return RedirectResponse(target + "cancelled")
    try:
        google_calendar.finish_auth(state, code)
    except Exception as exc:  # noqa: BLE001 - any OAuth failure becomes a friendly redirect
        log.warning("Calendar OAuth failed: %s", type(exc).__name__)
        return RedirectResponse(target + "error")
    return RedirectResponse(target + "connected")


@router.post("/disconnect")
def disconnect() -> dict[str, bool]:
    google_calendar.disconnect()
    return {"connected": False}


@router.get("/events", response_model=list[DayEventOut])
def events(day: str = "tomorrow") -> list[DayEventOut]:
    """The day's events as the planner sees them (titles are shown to you, never stored or sent to the AI)."""
    found, notice = google_calendar.events_for(daily.resolve_day(day))
    if notice:
        raise api_error(502, "calendar_error", notice, "Reconnect Google Calendar and try again.")
    return [DayEventOut(**e.public()) for e in found]
