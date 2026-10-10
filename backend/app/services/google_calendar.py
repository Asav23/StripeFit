"""Google Calendar (read-only): what's on tomorrow, so the outfit fits the day.

Privacy: the scope is calendar.events.readonly, the token is separate from Gmail's, and event titles
are only shown back to their owner. They are never sent to the AI and never stored: each event is
reduced to an occasion (by keywords) plus its start and end time.

Demo mode: DEMO_EVENTS (set on the AI log page / POST /api/debug/demo-calendar) stands in for a real
calendar, so the feature can be shown without a Google account.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Optional

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import CALENDAR_PENDING_PATH, CALENDAR_TOKEN_PATH, settings
from app.services.request_rules import classify_occasion

log = logging.getLogger("stripefit.calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar.events.readonly"]
MAX_EVENTS = 50
CACHE_SECONDS = 5 * 60
PENDING_TTL_SECONDS = 15 * 60
EVENT_FIELDS = "items(summary,location,start,end,status,attendees(self,responseStatus))"
CALENDAR_ERROR = "We couldn't read your calendar, so this is a plain casual outfit."

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# Demo stand-in: [{"title", "start": "HH:MM", "end": "HH:MM", "location"}] applied to whichever day is asked for.
DEMO_EVENTS: Optional[list[dict[str, Any]]] = None
_cache: dict[str, tuple[float, list["DayEvent"]]] = {}


@dataclass
class DayEvent:
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: Optional[str]
    occasion: Optional[str]

    def public(self) -> dict[str, Any]:
        """For the owner's own screen."""
        return {"title": self.title, "start": self.start.isoformat(), "end": self.end.isoformat(),
                "all_day": self.all_day, "location": self.location, "occasion": self.occasion}

    def private(self) -> dict[str, Any]:
        """What we store and what the AI sees: no title, no location text."""
        return {"occasion": self.occasion, "start": self.start.strftime("%H:%M"), "end": self.end.strftime("%H:%M"),
                "all_day": self.all_day}


# --------------------------------------------------------------------------- OAuth (same Google client as Gmail)


def _flow(state: Optional[str] = None) -> Flow:
    config = {"web": {
        "client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [settings.GOOGLE_CALENDAR_REDIRECT_URI],
    }}
    return Flow.from_client_config(config, scopes=SCOPES, state=state, redirect_uri=settings.GOOGLE_CALENDAR_REDIRECT_URI)


def _load_pending() -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(CALENDAR_PENDING_PATH.read_text())
    except (OSError, ValueError):
        return {}
    now = time.time()
    return {k: v for k, v in data.items() if now - v.get("created", 0) < PENDING_TTL_SECONDS}


def _save_pending(pending: dict[str, dict[str, Any]]) -> None:
    if pending:
        CALENDAR_PENDING_PATH.write_text(json.dumps(pending))
    else:
        CALENDAR_PENDING_PATH.unlink(missing_ok=True)


def auth_url() -> str:
    flow = _flow()
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="false")
    pending = _load_pending()
    pending[state] = {"verifier": flow.code_verifier, "created": time.time()}
    _save_pending(pending)
    return url


def finish_auth(state: str, code: str) -> None:
    pending = _load_pending()
    entry = pending.pop(state, None)
    _save_pending(pending)
    if entry is None:
        raise ValueError("Unknown or expired sign-in attempt.")
    flow = _flow(state=state)
    flow.code_verifier = entry["verifier"]
    flow.fetch_token(code=code)
    CALENDAR_TOKEN_PATH.write_text(flow.credentials.to_json())
    _cache.clear()


def credentials() -> Optional[Credentials]:
    if not settings.gmail_configured or not CALENDAR_TOKEN_PATH.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(CALENDAR_TOKEN_PATH), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            CALENDAR_TOKEN_PATH.write_text(creds.to_json())
    except (RefreshError, GoogleAuthError, ValueError):
        log.warning("Calendar token unusable; the user needs to reconnect")
        return None
    return creds if creds.valid else None


def connected() -> bool:
    return credentials() is not None


def disconnect() -> None:
    CALENDAR_TOKEN_PATH.unlink(missing_ok=True)
    _cache.clear()


# --------------------------------------------------------------------------- events


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=settings.tz)
    return start, start + timedelta(days=1)


def _classify(title: str, location: Optional[str]) -> Optional[str]:
    return classify_occasion(f"{title} {location or ''}")


def _demo_events(day: date) -> list[DayEvent]:
    events = []
    for e in DEMO_EVENTS or []:
        start = datetime.fromisoformat(f"{day.isoformat()}T{e['start']}").replace(tzinfo=settings.tz)
        end = datetime.fromisoformat(f"{day.isoformat()}T{e.get('end') or e['start']}").replace(tzinfo=settings.tz)
        end = end if end > start else start + timedelta(hours=2)
        events.append(DayEvent(e["title"], start, end, False, e.get("location"), _classify(e["title"], e.get("location"))))
    return sorted(events, key=lambda ev: ev.start)


def _fetch_raw(creds: Credentials, day: date) -> list[dict[str, Any]]:
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    start, end = _day_bounds(day)
    response = service.events().list(
        calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(), singleEvents=True,
        orderBy="startTime", maxResults=MAX_EVENTS, fields=EVENT_FIELDS,
    ).execute()
    return response.get("items", [])


def parse_raw(raw: list[dict[str, Any]], day: date) -> list[DayEvent]:
    """Google's event JSON -> DayEvents. Skips cancelled events and ones the user declined."""
    events = []
    day_start, day_end = _day_bounds(day)
    for item in raw:
        if item.get("status") == "cancelled":
            continue
        me = next((a for a in item.get("attendees") or [] if a.get("self")), None)
        if me and me.get("responseStatus") == "declined":
            continue
        title = (item.get("summary") or "Busy").strip()
        location = item.get("location")
        if "dateTime" in item.get("start", {}):
            start = datetime.fromisoformat(item["start"]["dateTime"]).astimezone(settings.tz)
            end = datetime.fromisoformat(item.get("end", {}).get("dateTime", item["start"]["dateTime"])).astimezone(settings.tz)
            all_day = False
        else:  # all-day event
            start, end, all_day = day_start, day_end, True
        events.append(DayEvent(title, start, end, all_day, location, _classify(title, location)))
    return sorted(events, key=lambda ev: ev.start)


def events_for(day: date) -> tuple[list[DayEvent], Optional[str]]:
    """(events, notice). Never raises: no calendar -> no events; a Google error -> no events + a notice."""
    if DEMO_EVENTS is not None:
        return _demo_events(day), None
    creds = credentials()
    if creds is None:
        return [], None
    key = day.isoformat()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1], None
    try:
        events = parse_raw(_fetch_raw(creds, day), day)
    except (HttpError, GoogleAuthError, OSError, ValueError, KeyError) as exc:
        log.warning("Calendar read failed: %s", type(exc).__name__)
        return [], CALENDAR_ERROR
    _cache[key] = (time.time(), events)
    return events, None
