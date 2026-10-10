"""The outfit of the day: planned from your calendar, the weather and your laundry, and sent the night before.

For a given day (today or tomorrow):
  1. Calendar (google_calendar.events_for): each event becomes an occasion. The most demanding one sets
     the outfit (an interview beats lectures); events that need different clothes get a packing tip.
     No calendar, or nothing clothes-related on it -> a casual day.
  2. Weather for the whole day, from the first event to the last (or 9am-7pm), at the main event's place.
  3. The normal pipeline: rules -> the user's taste -> AI stylist -> validated IDs -> rule-based fallback.
  4. Laundry tips: low on clean tops, or the right item is in the wash ("wash it tonight").
Daily outfits are Outfit rows (kind="daily", for_date). If the calendar changes, the outfit is rebuilt.

Notifications (services/scheduler.py calls run_due() every minute): the night before at evening_time
("Tomorrow's outfit") and/or the morning of at time ("Your outfit for today"), at most once each per day.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.config import settings
from app.errors import api_error
from app.models import Item, Outfit
from app.schemas import DailySettings, DailySettingsOut, ParsedRequest
from app.services import google_calendar, laundry, outfit_engine, push, rules
from app.services.google_calendar import DayEvent
from app.services.limits import get_user

log = logging.getLogger("stripefit.daily")

DAYS = ("today", "tomorrow")
CATCH_UP_HOURS = 3  # if the computer was asleep at notification time, still send within 3 hours
MIN_EVENT_HOURS = 2  # a 30-minute meeting still means wearing the outfit for a while
MAIN_SLOTS = ("top", "bottom", "one_piece")  # what "don't repeat yesterday" looks at
MORNING_TITLE = "Your outfit for today"
EVENING_TITLE = "Tomorrow's outfit"
CALENDAR_CHANGED = "Your calendar changed, so this outfit was updated."
MAX_NOTIFICATION_CHARS = 220


@dataclass
class DayPlan:
    day: date
    occasion: str
    start: datetime
    hours: float
    place: Optional[str]  # for the weather only; never sent to the AI
    events: list[DayEvent]
    summary: str  # e.g. "interview 10:00, football 19:00" (no event titles)
    notices: list[str] = field(default_factory=list)

    @property
    def signature(self) -> str:
        return signature(self.events)


def signature(events: list[DayEvent]) -> str:
    data = json.dumps([[e.occasion, e.start.isoformat(), e.end.isoformat(), e.location] for e in events])
    return hashlib.sha1(data.encode()).hexdigest()[:16]


def resolve_day(day: str, now: Optional[datetime] = None) -> date:
    now = now or datetime.now(settings.tz)
    if day not in DAYS:
        raise api_error(422, "invalid_day", "Pick today or tomorrow.")
    return now.date() + timedelta(days=DAYS.index(day))


def day_label(day: date, now: Optional[datetime] = None) -> str:
    today = (now or datetime.now(settings.tz)).date()
    return "today" if day == today else "tomorrow" if day == today + timedelta(days=1) else day.strftime("%A")


# --------------------------------------------------------------------------- planning a day


def plan_day(session: Session, day: date, now: Optional[datetime] = None) -> DayPlan:
    now = now or datetime.now(settings.tz)
    user = get_user(session)
    events, notice = google_calendar.events_for(day)
    notices = [notice] if notice else []
    relevant = [e for e in events if e.occasion]
    timed = [e for e in events if not e.all_day]

    if relevant:  # the most demanding event sets the outfit; an earlier one wins a tie
        anchor = max(relevant, key=lambda e: (rules.demand(e.occasion), -e.start.timestamp()))  # type: ignore[arg-type]
        occasion, place = anchor.occasion, anchor.location or user.daily_location
        for e in relevant:
            if e is not anchor and not rules.ranges_overlap(e.occasion, occasion):  # type: ignore[arg-type]
                tip = rules.PACK_TIPS.get(e.occasion, "a change of clothes")  # type: ignore[arg-type]
                notices.append(f"{rules.OCCASION_PHRASES.get(e.occasion, 'Your plan').capitalize()} at "
                               f"{e.start:%H:%M}: bring {tip}.")
        summary = ", ".join(f"{e.occasion.replace('_', ' ')} {'all day' if e.all_day else f'{e.start:%H:%M}'}"  # type: ignore[union-attr]
                            for e in relevant)
    else:
        occasion, place, summary = "casual", user.daily_location, "casual day"

    midnight = datetime(day.year, day.month, day.day, tzinfo=settings.tz)
    if timed:
        start = max(min(e.start for e in timed), midnight.replace(hour=rules.EARLIEST_DAY_START_HOUR))
        end = max(max(e.end for e in timed), start + timedelta(hours=MIN_EVENT_HOURS))
    else:
        start = midnight.replace(hour=rules.DAY_START_HOUR)
        end = start + timedelta(hours=rules.DAY_HOURS)
    if start < now:  # planning today, part-way through: from now on
        start = now.replace(second=0, microsecond=0)
        end = max(end, start + timedelta(hours=1))
    hours = max(1.0, min((end - start).total_seconds() / 3600, rules.MAX_DURATION_HOURS))
    return DayPlan(day, occasion, start, round(hours, 1), place, events, summary, notices)  # type: ignore[arg-type]


def _daily_for(session: Session, day: date) -> list[Outfit]:
    return list(session.exec(select(Outfit).where(Outfit.kind == "daily", Outfit.for_date == day.isoformat())
                             .order_by(col(Outfit.created_at).desc())).all())


def _main_ids(outfits: list[Outfit], slots: tuple[str, ...] = MAIN_SLOTS) -> set[int]:
    return {o.item_ids[s] for o in outfits for s in slots if o.item_ids.get(s)}


def make(session: Session, day: date, *, another: bool = False, extra_notices: Optional[list[str]] = None) -> Outfit:
    """Build the outfit for `day`. Raises the usual friendly 409s if the wardrobe is empty or all in the wash."""
    wardrobe = outfit_engine.usable_wardrobe(session)
    now = datetime.now(settings.tz)
    plan = plan_day(session, day, now)
    exclude = _main_ids(_daily_for(session, day - timedelta(days=1)))  # don't repeat yesterday's main pieces
    if another:  # avoid everything already suggested for this day
        exclude |= _main_ids(_daily_for(session, day), MAIN_SLOTS + ("outerwear", "shoes"))

    label = day_label(day, now)
    parsed = ParsedRequest(occasion=plan.occasion, occasion_detail=plan.summary,  # type: ignore[arg-type]
                           datetime_iso=plan.start.isoformat(timespec="minutes"), duration_hours=plan.hours,
                           setting="mixed", activity="unknown")
    extra = {"day_events": [e.private() for e in plan.events], "calendar_signature": plan.signature}
    outfit = outfit_engine.build_outfit(
        session, wardrobe, f"{label.capitalize()}: {plan.summary}", parsed, kind="daily", for_date=day.isoformat(),
        exclude_ids=exclude, notices=(extra_notices or []) + plan.notices, extra=extra, weather_place=plan.place,
    )
    tips = laundry.advice(wardrobe, set(outfit_engine._all_ids(outfit.item_ids)), outfit.parsed, outfit.weather, label)
    if tips:
        outfit.notices = outfit.notices + tips
        session.add(outfit)
        session.commit()
        session.refresh(outfit)
    return outfit


def get_or_make(session: Session, day: date) -> tuple[Outfit, list[DayEvent]]:
    """The day's outfit; rebuilt if the calendar changed since it was made."""
    events, _ = google_calendar.events_for(day)
    existing = _daily_for(session, day)
    if existing:
        latest = existing[0]
        if latest.parsed.get("calendar_signature", signature([])) == signature(events):
            return latest, events
        return make(session, day, extra_notices=[CALENDAR_CHANGED]), events
    return make(session, day), events


# --------------------------------------------------------------------------- settings


def settings_out(session: Session) -> DailySettingsOut:
    user = get_user(session)
    return DailySettingsOut(
        enabled=user.daily_enabled, time=user.daily_time, location=user.daily_location,
        evening_enabled=user.evening_enabled, evening_time=user.evening_time,
        push_configured=push.configured(), subscriptions=push.count(session),
        last_sent_date=user.daily_last_sent, evening_last_sent=user.evening_last_sent,
        calendar_connected=google_calendar.connected(),
    )


def update_settings(session: Session, body: DailySettings) -> DailySettingsOut:
    user = get_user(session)
    now = datetime.now(settings.tz)
    today = now.date().isoformat()
    # Switched on after today's window has passed: start next time, don't ping right now.
    if body.enabled and not user.daily_enabled and _past_catch_up(now, body.time):
        user.daily_last_sent = today
    if body.evening_enabled and not user.evening_enabled and _past_catch_up(now, body.evening_time):
        user.evening_last_sent = today
    user.daily_enabled, user.daily_time, user.daily_location = body.enabled, body.time, body.location
    user.evening_enabled, user.evening_time = body.evening_enabled, body.evening_time
    session.add(user)
    session.commit()
    return settings_out(session)


# --------------------------------------------------------------------------- notifications


def _weather_bit(weather: Optional[dict[str, Any]]) -> str:
    if not weather:
        return "No forecast"
    low = round(weather.get("temperature_min_c") if weather.get("temperature_min_c") is not None else weather["temperature_c"])
    high = round(weather.get("temperature_max_c") if weather.get("temperature_max_c") is not None else weather["temperature_c"])
    temps = f"{low}°C" if low == high else f"{low}–{high}°C"
    if weather.get("is_wet"):
        return f"{temps}, rain from {weather['rain_from']}" if weather.get("rain_from") else f"{temps}, rain likely"
    return f"{temps}, {weather['description'].lower()}"


def notification_body(session: Session, outfit: Outfit) -> str:
    names = [item.name.lower() for i in outfit_engine._all_ids(outfit.item_ids) if (item := session.get(Item, i))]
    summary = outfit.parsed.get("occasion_detail") or "your day"
    body = f"{_weather_bit(outfit.weather)}. {summary.capitalize()}: {', '.join(names)}."
    tip = next((n for n in outfit.notices if "wash" in n.lower() or "bring" in n.lower()), None) or next(iter(outfit.gaps), None)
    if tip:
        body += f" {tip}"
    return body if len(body) <= MAX_NOTIFICATION_CHARS else body[: MAX_NOTIFICATION_CHARS - 1] + "…"


def notify(session: Session, day: date, title: str) -> tuple[int, int]:
    """Make sure the day's outfit exists and push it to every subscribed browser. Returns (sent, removed)."""
    outfit, _ = get_or_make(session, day)
    which = "today" if day == datetime.now(settings.tz).date() else "tomorrow"
    return push.send_all(session, title, notification_body(session, outfit), url=f"/today?day={which}")


def _at(now: datetime, hh_mm: str) -> datetime:
    hour, minute = (int(x) for x in hh_mm.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _past_catch_up(now: datetime, hh_mm: str) -> bool:
    return now >= _at(now, hh_mm) + timedelta(hours=CATCH_UP_HOURS)


def _due(now: datetime, enabled: bool, hh_mm: str, last_sent: Optional[str]) -> bool:
    return enabled and last_sent != now.date().isoformat() and _at(now, hh_mm) <= now and not _past_catch_up(now, hh_mm)


def _send(session: Session, day: date, title: str, what: str) -> None:
    try:
        sent, removed = notify(session, day, title)
        log.info("%s outfit for %s: notified %d browser(s), removed %d expired", what, day, sent, removed)
    except HTTPException as exc:  # empty wardrobe / everything in the wash: nothing to suggest
        log.info("%s outfit for %s skipped: %s", what, day, exc.detail)


def run_if_due(session: Session, now: Optional[datetime] = None) -> bool:
    """Morning notification: today's outfit. At most once a day."""
    now = now or datetime.now(settings.tz)
    user = get_user(session)
    if not _due(now, user.daily_enabled, user.daily_time, user.daily_last_sent):
        return False
    user.daily_last_sent = now.date().isoformat()  # mark first: a failure must not repeat every minute
    session.add(user)
    session.commit()
    _send(session, now.date(), MORNING_TITLE, "Morning")
    return True


def run_evening_if_due(session: Session, now: Optional[datetime] = None) -> bool:
    """Night-before notification: tomorrow's outfit and tomorrow's weather. At most once an evening."""
    now = now or datetime.now(settings.tz)
    user = get_user(session)
    if not _due(now, user.evening_enabled, user.evening_time, user.evening_last_sent):
        return False
    user.evening_last_sent = now.date().isoformat()
    session.add(user)
    session.commit()
    _send(session, now.date() + timedelta(days=1), EVENING_TITLE, "Evening")
    return True
