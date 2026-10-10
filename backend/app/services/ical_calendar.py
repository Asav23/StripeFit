"""Calendar via a private iCal link (no Google Cloud project, no OAuth).

Google Calendar (Settings -> your calendar -> Integrate calendar -> "Secret address in iCal format"),
Outlook and iCloud all publish a private read-only .ics link. Whoever has the link can read the calendar,
so it is treated like a password: stored in a gitignored file (never the DB or git), never logged, never
sent to the AI, and only fetched from known calendar hosts over https (no arbitrary URLs: no SSRF).
Events are reduced to occasions exactly like the Google sign-in path (google_calendar.DayEvent).
"""

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import recurring_ical_events
from icalendar import Calendar

from app.config import CALENDAR_ICAL_PATH, settings
from app.services.google_calendar import DayEvent, _classify

log = logging.getLogger("stripefit.ical")

ALLOWED_HOSTS = ("calendar.google.com", "outlook.office365.com", "outlook.live.com", "outlook.office.com")
ALLOWED_HOST_SUFFIXES = (".icloud.com",)  # iCloud: pXX-caldav.icloud.com
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15
CACHE_SECONDS = 15 * 60  # Google only refreshes the feed every few hours anyway
FETCH_ERROR = "We couldn't read your calendar link, so this is a plain casual outfit."

_cache: dict[str, Any] = {}  # {"at": float, "calendar": Calendar}


class BadLink(ValueError):
    """User-facing reason a pasted link can't be used."""


def normalise(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host in ALLOWED_HOSTS or host.endswith(ALLOWED_HOST_SUFFIXES)):
        raise BadLink("Paste the private iCal link from Google Calendar, Outlook or iCloud (it starts with https://).")
    if "calendar.google.com" in host and "/ical/" not in parsed.path:
        raise BadLink("That's not the iCal link. In Google Calendar: Settings → your calendar → "
                      "Integrate calendar → “Secret address in iCal format”.")
    return url


def _fetch(url: str) -> Calendar:
    with httpx.stream("GET", url, timeout=TIMEOUT_SECONDS, follow_redirects=False) as response:
        if response.status_code in (401, 403, 404):
            raise BadLink("That link doesn't work any more. Copy the secret address again (it may have been reset).")
        response.raise_for_status()
        data = b""
        for chunk in response.iter_bytes():
            data += chunk
            if len(data) > MAX_BYTES:
                raise BadLink("That calendar is too big to read.")
    try:
        return Calendar.from_ical(data)
    except ValueError as exc:
        raise BadLink("That link isn't an iCal calendar.") from exc


def link() -> Optional[str]:
    try:
        value = CALENDAR_ICAL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def connected() -> bool:
    return link() is not None


def save_link(url: str) -> int:
    """Check the link really works, then store it. Returns how many events it holds."""
    url = normalise(url)
    try:
        calendar = _fetch(url)
    except httpx.HTTPError as exc:
        raise BadLink("Couldn't reach that calendar. Check the link and your connection.") from exc
    CALENDAR_ICAL_PATH.write_text(url, encoding="utf-8")
    _cache.clear()
    _cache.update(at=time.time(), calendar=calendar)
    return len(calendar.walk("VEVENT"))


def remove_link() -> None:
    CALENDAR_ICAL_PATH.unlink(missing_ok=True)
    _cache.clear()


def _calendar() -> Calendar:
    if _cache.get("calendar") is not None and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["calendar"]
    url = link()
    if url is None:
        raise BadLink("No calendar link saved.")
    calendar = _fetch(url)
    _cache.update(at=time.time(), calendar=calendar)
    return calendar


def _as_dublin(value: Any) -> tuple[datetime, bool]:
    """(datetime in Dublin, all_day). Dates are all-day; floating times are taken as Dublin time."""
    if isinstance(value, datetime):
        return (value.astimezone(settings.tz) if value.tzinfo else value.replace(tzinfo=settings.tz)), False
    return datetime(value.year, value.month, value.day, tzinfo=settings.tz), True


def parse(calendar: Calendar, day: date) -> list[DayEvent]:
    """Events overlapping `day` (recurring ones expanded), as DayEvents. Cancelled ones are skipped."""
    start = datetime(day.year, day.month, day.day, tzinfo=settings.tz)
    end = start + timedelta(days=1)
    events = []
    for item in recurring_ical_events.of(calendar).between(start, end):
        if str(item.get("STATUS", "")).upper() == "CANCELLED":
            continue
        title = str(item.get("SUMMARY") or "Busy").strip()
        location = str(item.get("LOCATION") or "").strip() or None
        ev_start, all_day = _as_dublin(item.decoded("DTSTART"))
        ev_end = _as_dublin(item.decoded("DTEND"))[0] if item.get("DTEND") else ev_start + timedelta(hours=1)
        if all_day:
            ev_start, ev_end = start, end
        events.append(DayEvent(title, ev_start, ev_end, all_day, location, _classify(title, location)))
    return sorted(events, key=lambda e: e.start)


def events_for(day: date) -> tuple[list[DayEvent], Optional[str]]:
    """(events, notice). Never raises."""
    try:
        return parse(_calendar(), day), None
    except (BadLink, httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("Calendar link read failed: %s", type(exc).__name__)  # never log the link itself
        return [], FETCH_ERROR
