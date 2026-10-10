"""The casual fit of the day: one ready-made outfit every day, plus an optional morning notification.

It runs the same pipeline as a planned outfit (weather for the whole day -> rules -> the user's taste
-> AI stylist -> validated IDs -> rule-based fallback), with the request built in code instead of
parsed, so it costs one AI call a day. "Another option" makes a new one that avoids today's earlier
picks; yesterday's main pieces are avoided too, so the week doesn't repeat itself.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.config import settings
from app.models import Item, Outfit
from app.schemas import DailySettings, DailySettingsOut, ParsedRequest
from app.services import outfit_engine, push
from app.services.limits import get_user

log = logging.getLogger("stripefit.daily")

DAILY_START_HOUR = 9  # the outfit covers the day from 9am (or from now, if later)
DAILY_HOURS = 10  # weather window: 9am-7pm
CATCH_UP_HOURS = 3  # if the computer was asleep at notification time, still send within 3 hours
MAIN_SLOTS = ("top", "bottom", "one_piece")  # what "don't repeat yesterday" looks at
NOTIFICATION_TITLE = "Your casual fit for today"
MAX_NOTIFICATION_CHARS = 140


def today(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(settings.tz)).date().isoformat()


def settings_out(session: Session) -> DailySettingsOut:
    user = get_user(session)
    return DailySettingsOut(enabled=user.daily_enabled, time=user.daily_time, location=user.daily_location,
                            push_configured=push.configured(), subscriptions=push.count(session),
                            last_sent_date=user.daily_last_sent)


def update_settings(session: Session, body: DailySettings) -> DailySettingsOut:
    user = get_user(session)
    now = datetime.now(settings.tz)
    if body.enabled and not user.daily_enabled and _past_catch_up(now, body.time):
        user.daily_last_sent = today(now)  # switched on after today's window: start tomorrow, don't ping now
    user.daily_enabled, user.daily_time, user.daily_location = body.enabled, body.time, body.location
    session.add(user)
    session.commit()
    return settings_out(session)


def _daily_for(session: Session, date: str) -> list[Outfit]:
    return list(session.exec(select(Outfit).where(Outfit.kind == "daily", Outfit.for_date == date)
                             .order_by(col(Outfit.created_at).desc())).all())


def _main_ids(outfits: list[Outfit], slots: tuple[str, ...] = MAIN_SLOTS) -> set[int]:
    return {o.item_ids[s] for o in outfits for s in slots if o.item_ids.get(s)}


def make(session: Session, *, another: bool = False) -> Outfit:
    """Create today's casual fit. Raises the usual friendly 409s if the wardrobe is empty or all in the wash."""
    wardrobe = outfit_engine.usable_wardrobe(session)
    user = get_user(session)
    now = datetime.now(settings.tz)
    date = today(now)
    yesterday = (now - timedelta(days=1)).date().isoformat()
    exclude = _main_ids(_daily_for(session, yesterday))
    if another:  # avoid everything from today's earlier options, not just the main pieces
        exclude |= _main_ids(_daily_for(session, date), MAIN_SLOTS + ("outerwear", "shoes"))

    start = max(now, now.replace(hour=DAILY_START_HOUR, minute=0, second=0, microsecond=0))
    where = user.daily_location
    parsed = ParsedRequest(occasion="casual", occasion_detail="Casual day", destination=where,
                           datetime_iso=start.isoformat(timespec="minutes"), setting="mixed", activity="walking",
                           duration_hours=max(1, min(DAILY_HOURS, 24 - start.hour)))
    text = f"Casual day{f' in {where}' if where else ''}"
    return outfit_engine.build_outfit(session, wardrobe, text, parsed, kind="daily", for_date=date, exclude_ids=exclude)


def get_or_make(session: Session) -> Outfit:
    existing = _daily_for(session, today())
    return existing[0] if existing else make(session)


def notification_body(session: Session, outfit: Outfit) -> str:
    names = [session.get(Item, i).name.lower() for i in outfit_engine._all_ids(outfit.item_ids)  # type: ignore[union-attr]
             if session.get(Item, i)]
    weather = outfit.weather
    lead = f"{round(weather['temperature_c'])}°C, {weather['description'].lower()}: " if weather else ""
    body = lead + ", ".join(names)
    return body if len(body) <= MAX_NOTIFICATION_CHARS else body[: MAX_NOTIFICATION_CHARS - 1] + "…"


def notify(session: Session) -> tuple[int, int]:
    """Make sure today's fit exists and push it to every subscribed browser. Returns (sent, removed)."""
    outfit = get_or_make(session)
    return push.send_all(session, NOTIFICATION_TITLE, notification_body(session, outfit), url="/plan?daily=1")


def _at(now: datetime, hh_mm: str) -> datetime:
    hour, minute = (int(x) for x in hh_mm.split(":"))
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _past_catch_up(now: datetime, hh_mm: str) -> bool:
    return now >= _at(now, hh_mm) + timedelta(hours=CATCH_UP_HOURS)


def run_if_due(session: Session, now: Optional[datetime] = None) -> bool:
    """Called by the scheduler every minute. Sends at most one morning notification per day."""
    now = now or datetime.now(settings.tz)
    user = get_user(session)
    date = today(now)
    if not user.daily_enabled or user.daily_last_sent == date or now < _at(now, user.daily_time):
        return False
    if _past_catch_up(now, user.daily_time):
        return False
    user.daily_last_sent = date  # mark first: a failure must not turn into a notification every minute
    session.add(user)
    session.commit()
    try:
        sent, removed = notify(session)
        log.info("Daily fit for %s: notified %d browser(s), removed %d expired", date, sent, removed)
    except HTTPException as exc:  # empty wardrobe / everything in the wash: nothing to suggest today
        log.info("Daily fit skipped for %s: %s", date, exc.detail)
    return True
