"""Database tables (SQLModel on SQLite)."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; everything we store is UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


# Allowed values. Kept here so models, schemas and the UI agree.
CATEGORIES = ["top", "bottom", "one_piece", "outerwear", "shoes", "accessory", "sportswear"]
OWNERS = ["me", "child", "other", "unknown"]
STATUSES = ["available", "worn", "in_wash", "unavailable", "on_the_way", "returned"]
SOURCES = ["photo", "email", "gmail", "manual"]


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    image_path: Optional[str] = None  # relative to uploads/, e.g. "originals/abc.jpg"
    thumb_path: Optional[str] = None
    image_hash: Optional[str] = None  # perceptual hash of a real photo (None for placeholders)
    has_real_photo: bool = False

    category: str = "unknown"  # one of CATEGORIES, or "unknown" while pending review
    colours: list[str] = Field(default_factory=lambda: ["unknown"], sa_column=Column(JSON))
    formality: Optional[int] = None  # 1 gym/lounge .. 3 smart casual .. 5 black tie
    warmth: Optional[int] = None  # 1 very light .. 5 very warm
    waterproof: Optional[bool] = None
    material: Optional[str] = None

    owner: str = "me"
    status: str = "available"
    confirmed: bool = False  # False = in the review queue
    dismissed: bool = False  # rejected/refunded before confirming; kept so re-imports don't re-add it
    confidence: Optional[float] = None
    notes: Optional[str] = None  # AI notes / review prompts ("Is this yours?")

    source: str = "manual"
    source_ref: Optional[str] = Field(default=None, index=True)  # retailer|order_id|name|size
    order_qty: Optional[int] = None  # units of this line in the order (so 2 identical tees aren't "duplicates")
    retailer: Optional[str] = None
    size: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None

    last_worn: Optional[datetime] = None
    wears_since_wash: int = 0  # jeans and jackets get several wears; see rules.WEARS_BEFORE_WASH
    created_at: datetime = Field(default_factory=utcnow)


class Outfit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    request_text: str
    parsed: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    weather: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    item_ids: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # slot -> id (accessory -> [ids])
    explanation: str = ""
    gaps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    notices: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    used_fallback: bool = False
    feedback: Optional[str] = None  # "up" | "down" | None
    worn: bool = False
    kind: str = Field(default="plan", index=True)  # "plan" (asked for) | "daily" (casual fit of the day)
    for_date: Optional[str] = Field(default=None, index=True)  # daily outfits: Dublin date YYYY-MM-DD
    created_at: datetime = Field(default_factory=utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)  # single demo user, id=1
    premium: bool = False
    premium_since: Optional[datetime] = None

    # Style preferences the user states (learned ones come from StyleSignal).
    favourite_colours: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    avoid_colours: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    style_notes: Optional[str] = None

    # Daily casual fit
    daily_enabled: bool = False
    daily_time: str = "08:00"  # Europe/Dublin
    daily_location: Optional[str] = None  # None = default city
    daily_last_sent: Optional[str] = None  # Dublin date of the last morning notification
    evening_enabled: bool = False  # the night-before notification ("what to wear tomorrow")
    evening_time: str = "20:00"
    evening_last_sent: Optional[str] = None  # Dublin date of the evening it was last sent


class StyleSignal(SQLModel, table=True):
    """One thing the user did that tells us about their taste. The style profile is built from these."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, index=True)
    kind: str  # one of SIGNAL_KINDS
    item_id: Optional[int] = Field(default=None, index=True)
    outfit_id: Optional[int] = None
    occasion: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


SIGNAL_KINDS = ["thumbs_up", "thumbs_down", "swap_out", "swap_in", "worn"]


class PushSubscription(SQLModel, table=True):
    """A browser that asked for the morning notification (Web Push)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(default=1, index=True)
    endpoint: str = Field(unique=True, index=True)
    p256dh: str
    auth: str
    created_at: datetime = Field(default_factory=utcnow)


class Purchase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    stripe_session_id: str = Field(unique=True, index=True)
    amount_total: Optional[int] = None  # minor units (cents)
    currency: Optional[str] = None
    status: str = "paid"
    created_at: datetime = Field(default_factory=utcnow)


class AICall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    model: str
    latency_ms: int = 0
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class IngestLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # "email" | "gmail"
    ref: str = Field(index=True)  # filename or Gmail message ID
    email_type: Optional[str] = None
    items_found: int = 0
    items_skipped: int = 0
    notes: list[str] = Field(default_factory=list, sa_column=Column(JSON))  # skip reasons
    created_at: datetime = Field(default_factory=utcnow)
