"""Pydantic schemas: API requests/responses and the AI output contracts.

AI output schemas are deliberately lenient on *format* (they normalise "unknown",
synonyms and casing) but strict on *values*: anything we can't map stays unknown/None.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.models import CATEGORIES, as_utc

Category = Literal["top", "bottom", "one_piece", "outerwear", "shoes", "accessory", "sportswear", "unknown"]
Owner = Literal["me", "child", "other", "unknown"]
Status = Literal["available", "worn", "in_wash", "unavailable", "on_the_way", "returned"]
Occasion = Literal["uni", "casual", "night_out", "date", "interview", "work", "wedding", "funeral", "sport",
                   "debs", "society", "match", "festival", "travel", "presentation", "other"]
Setting = Literal["indoor", "outdoor", "mixed", "unknown"]
Activity = Literal["sitting", "standing", "dancing", "walking", "active", "unknown"]
OCCASION_SYNONYMS = {
    "ball": "debs", "formal": "debs", "prom": "debs", "lecture": "uni", "college": "uni", "class": "uni",
    "gym": "sport", "training": "sport", "game": "match", "party": "night_out", "club": "night_out",
    "nightout": "night_out", "job_interview": "interview", "trip": "travel", "flight": "travel",
    "talk": "presentation", "societies": "society", "soc": "society", "everyday": "casual",
}
TravelMode = Literal["walk", "cycle", "bus", "train", "car", "unknown"]
Slot = Literal["top", "bottom", "one_piece", "outerwear", "shoes", "accessory"]

_UNKNOWN_STRINGS = {"", "unknown", "none", "null", "n/a", "na", "not sure", "unsure", "?"}

_CATEGORY_SYNONYMS = {
    "tops": "top", "shirt": "top", "t-shirt": "top", "tshirt": "top", "blouse": "top", "jumper": "top",
    "sweater": "top", "knitwear": "top", "hoodie": "top",
    "bottoms": "bottom", "trousers": "bottom", "jeans": "bottom", "pants": "bottom", "skirt": "bottom",
    "shorts": "bottom",
    "dress": "one_piece", "jumpsuit": "one_piece", "playsuit": "one_piece", "one-piece": "one_piece",
    "onepiece": "one_piece", "suit": "one_piece",
    "jacket": "outerwear", "coat": "outerwear", "blazer": "outerwear", "outer": "outerwear",
    "footwear": "shoes", "shoe": "shoes", "boots": "shoes", "trainers": "shoes", "sneakers": "shoes",
    "accessories": "accessory", "bag": "accessory", "belt": "accessory", "scarf": "accessory", "hat": "accessory",
    "tie": "accessory", "jewellery": "accessory", "jewelry": "accessory",
    "activewear": "sportswear", "sport": "sportswear", "gym": "sportswear", "athletic": "sportswear",
}


def is_unknown(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in _UNKNOWN_STRINGS)


def normalise_category(value: Any) -> str:
    if is_unknown(value):
        return "unknown"
    text = str(value).strip().lower().replace(" ", "_")
    if text in CATEGORIES:
        return text
    return _CATEGORY_SYNONYMS.get(text.replace("_", "-"), _CATEGORY_SYNONYMS.get(text, "unknown"))


def normalise_colours(value: Any) -> list[str]:
    if value is None:
        return ["unknown"]
    if isinstance(value, str):
        value = [part for part in value.replace("/", ",").split(",")]
    colours = [str(c).strip().lower() for c in value if not is_unknown(c)]
    return colours[:4] or ["unknown"]


def none_if_unknown(value: Any) -> Any:
    return None if is_unknown(value) else value


def clamp_scale(value: Any) -> Optional[int]:
    """1-5 scales: anything unparseable or out of range becomes None (unknown)."""
    if is_unknown(value):
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 5 else None


# --------------------------------------------------------------------------- AI output


class ClothingLabels(BaseModel):
    name: str = "Unnamed item"
    category: Category = "unknown"
    colours: list[str] = Field(default_factory=lambda: ["unknown"])
    formality: Optional[int] = None
    warmth: Optional[int] = None
    waterproof: Optional[bool] = None
    material: Optional[str] = None
    is_clothing: bool = True
    confidence: float = Field(default=0.5, ge=0, le=1)
    notes: Optional[str] = None

    _cat = field_validator("category", mode="before")(normalise_category)
    _col = field_validator("colours", mode="before")(normalise_colours)
    _scale = field_validator("formality", "warmth", mode="before")(clamp_scale)
    _unk = field_validator("material", "notes", "waterproof", mode="before")(none_if_unknown)


class ParsedRequest(BaseModel):
    occasion: Occasion = "other"
    occasion_detail: Optional[str] = None
    destination: Optional[str] = None
    datetime_iso: str
    travel_mode: TravelMode = "unknown"
    dress_code: Optional[str] = None
    needs_clarification: Optional[str] = None
    setting: Setting = "unknown"  # indoor / outdoor / mixed
    duration_hours: Optional[float] = None  # how long the event lasts, if the note says
    activity: Activity = "unknown"  # mostly sitting, standing, dancing, walking, or active

    @field_validator("occasion", mode="before")
    @classmethod
    def _occasion(cls, value: Any) -> Any:
        """Map synonyms; anything else unrecognised becomes "other" instead of failing the whole parse."""
        if not isinstance(value, str):
            return value
        text = value.strip().lower().replace(" ", "_").replace("-", "_")
        text = OCCASION_SYNONYMS.get(text, text)
        return text if text in Occasion.__args__ else "other"  # type: ignore[attr-defined]

    @field_validator("setting", "activity", mode="before")
    @classmethod
    def _known_or_unknown(cls, value: Any, info: Any) -> Any:
        allowed = (Setting if info.field_name == "setting" else Activity).__args__  # type: ignore[attr-defined]
        text = value.strip().lower() if isinstance(value, str) else "unknown"
        return text if text in allowed else "unknown"

    @field_validator("duration_hours", mode="before")
    @classmethod
    def _hours(cls, value: Any) -> Optional[float]:
        if is_unknown(value):
            return None
        try:
            hours = float(value)
        except (TypeError, ValueError):
            return None
        return hours if 0 < hours <= 24 else None

    _unk = field_validator("occasion_detail", "destination", "dress_code", "needs_clarification", mode="before")(
        none_if_unknown
    )

    @field_validator("travel_mode", mode="before")
    @classmethod
    def _lower(cls, value: Any) -> Any:
        return value.strip().lower().replace(" ", "_").replace("-", "_") if isinstance(value, str) else value

    @field_validator("datetime_iso")
    @classmethod
    def _valid_iso(cls, value: str) -> str:
        datetime.fromisoformat(value)  # raises ValueError -> validation error -> AI retry
        return value


class OutfitPick(BaseModel):
    top_id: Optional[int] = None
    bottom_id: Optional[int] = None
    one_piece_id: Optional[int] = None
    outerwear_id: Optional[int] = None
    shoes_id: Optional[int] = None
    accessory_ids: list[int] = Field(default_factory=list)
    explanation: str = ""
    confidence: Optional[float] = None

    @field_validator("accessory_ids", mode="before")
    @classmethod
    def _none_list(cls, value: Any) -> Any:
        return [] if value is None else value


class ExtractedItem(BaseModel):
    name: str
    category: Category = "unknown"
    colours: list[str] = Field(default_factory=lambda: ["unknown"])
    size: Optional[str] = None
    quantity: int = 1
    price: Optional[float] = None
    is_clothing: bool = True
    likely_for: Literal["me", "child", "gift", "unknown"] = "unknown"
    image_url: Optional[str] = None
    status_hint: Literal["kept", "cancelled", "out_of_stock", "unknown"] = "unknown"
    exchange_role: Optional[Literal["old", "new"]] = None  # only for exchange emails

    _cat = field_validator("category", mode="before")(normalise_category)
    _col = field_validator("colours", mode="before")(normalise_colours)
    _unk = field_validator("size", "image_url", "price", "exchange_role", mode="before")(none_if_unknown)

    @field_validator("quantity", mode="before")
    @classmethod
    def _qty(cls, value: Any) -> int:
        try:
            return max(1, min(int(value), 10))  # cap: a single order line never needs >10 units
        except (TypeError, ValueError):
            return 1


class OrderExtraction(BaseModel):
    email_type: Literal[
        "order_confirmation", "dispatch", "delivery", "refund", "return", "cancellation", "exchange", "marketing", "other"
    ] = "other"
    retailer: Optional[str] = None
    order_id: Optional[str] = None
    currency: Optional[str] = None
    order_date: Optional[str] = None
    items: list[ExtractedItem] = Field(default_factory=list, max_length=25)
    confidence: float = Field(default=0.5, ge=0, le=1)

    _unk = field_validator("retailer", "order_id", "currency", "order_date", mode="before")(none_if_unknown)


# --------------------------------------------------------------------------- API


class ItemOut(BaseModel):
    id: int
    name: str
    image_url: Optional[str]
    thumb_url: Optional[str]
    has_real_photo: bool
    category: str
    colours: list[str]
    formality: Optional[int]
    warmth: Optional[int]
    waterproof: Optional[bool]
    material: Optional[str]
    owner: str
    status: str
    confirmed: bool
    confidence: Optional[float]
    notes: Optional[str]
    source: str
    source_ref: Optional[str]
    retailer: Optional[str]
    size: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    last_worn: Optional[datetime]
    created_at: datetime

    _utc = field_validator("last_worn", "created_at")(as_utc)


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: Category
    colours: list[str] = Field(default_factory=lambda: ["unknown"])
    formality: Optional[int] = Field(default=None, ge=1, le=5)
    warmth: Optional[int] = Field(default=None, ge=1, le=5)
    waterproof: Optional[bool] = None
    material: Optional[str] = None
    owner: Owner = "me"
    status: Status = "available"
    retailer: Optional[str] = None
    size: Optional[str] = None


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[Category] = None
    colours: Optional[list[str]] = None
    formality: Optional[int] = Field(default=None, ge=1, le=5)
    warmth: Optional[int] = Field(default=None, ge=1, le=5)
    waterproof: Optional[bool] = None
    material: Optional[str] = None
    owner: Optional[Owner] = None
    status: Optional[Status] = None
    retailer: Optional[str] = None
    size: Optional[str] = None


class StatusUpdate(BaseModel):
    status: Status


class IdList(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class DuplicateOut(BaseModel):
    item: ItemOut
    level: Literal["definite", "likely", "possible"]
    reason: str


class ReviewItemOut(ItemOut):
    duplicate: Optional[DuplicateOut] = None
    missing_fields: list[str] = Field(default_factory=list)  # "please fill in"
    low_confidence: bool = False
    prompt: Optional[str] = None  # e.g. "Is this yours?"


class ConfirmRequest(ItemUpdate):
    duplicate_decision: Optional[Literal["merge", "keep_both"]] = None
    merge_target_id: Optional[int] = None


class PurchaseOut(BaseModel):
    stripe_session_id: str
    amount_total: Optional[int]
    currency: Optional[str]
    status: str
    created_at: datetime

    _utc = field_validator("created_at")(as_utc)


class MeOut(BaseModel):
    premium: bool
    premium_since: Optional[datetime]
    confirmed_item_count: int
    pending_count: int
    item_limit: Optional[int]  # None = unlimited (Pro)
    mock_ai: bool
    stripe_configured: bool
    gmail_configured: bool
    latest_purchase: Optional[PurchaseOut]

    _utc = field_validator("premium_since")(as_utc)


class PlanRequest(BaseModel):
    request_text: str = Field(max_length=500)


class WeatherOut(BaseModel):
    location_name: str
    time: str
    temperature_c: float
    precipitation_probability: Optional[int]
    precipitation_mm: Optional[float]
    wind_kmh: Optional[float]
    weather_code: Optional[int]
    description: str
    icon: str
    is_wet: bool
    # Across the whole event (None on outfits saved before this existed):
    window_hours: Optional[float] = None
    temperature_min_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    precipitation_probability_max: Optional[int] = None


class OutfitSlotOut(BaseModel):
    slot: Slot
    item: ItemOut


class OutfitOut(BaseModel):
    id: int
    request_text: str
    parsed: dict[str, Any]
    weather: Optional[WeatherOut]
    slots: list[OutfitSlotOut]
    explanation: str
    gaps: list[str]
    notices: list[str]
    used_fallback: bool
    feedback: Optional[str]
    worn: bool
    created_at: datetime
    kind: str = "plan"  # "plan" (asked for) | "daily" (the casual fit of the day)
    for_date: Optional[str] = None  # daily outfits: the Dublin date, YYYY-MM-DD

    _utc = field_validator("created_at")(as_utc)


class PlanResponse(BaseModel):
    outfit: Optional[OutfitOut] = None
    clarification: Optional[str] = None


class SwapRequest(BaseModel):
    slot: Slot


class FeedbackRequest(BaseModel):
    feedback: Optional[Literal["up", "down"]]


class PhotoResult(BaseModel):
    filename: str
    ok: bool
    item: Optional[ItemOut] = None
    message: str


class FileIngestResult(BaseModel):
    filename: str
    email_type: Optional[str] = None
    retailer: Optional[str] = None
    order_id: Optional[str] = None
    items_created: int = 0
    items_updated: int = 0
    items_skipped: int = 0
    notes: list[str] = Field(default_factory=list)


class IngestSummary(BaseModel):
    files: list[FileIngestResult]
    items_created: int
    items_updated: int
    skipped: dict[str, int]  # reason -> count
    summary: str


# --------------------------------------------------------------------------- personal style


class StylePreferences(BaseModel):
    """What the user tells us directly. Learned signals are added on top (see services/style_profile.py)."""
    favourite_colours: list[str] = Field(default_factory=list, max_length=10)
    avoid_colours: list[str] = Field(default_factory=list, max_length=10)
    style_notes: Optional[str] = Field(default=None, max_length=300)  # e.g. "I prefer relaxed fits"

    @field_validator("favourite_colours", "avoid_colours", mode="before")
    @classmethod
    def _clean(cls, value: Any) -> list[str]:
        items = value.split(",") if isinstance(value, str) else (value or [])
        return [str(c).strip().lower() for c in items if str(c).strip()][:10]


# --------------------------------------------------------------------------- daily casual fit + notifications


class DailySettings(BaseModel):
    enabled: bool = False  # send a notification every morning
    time: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # Europe/Dublin
    location: Optional[str] = Field(default=None, max_length=80)  # None = the default city

    _unk = field_validator("location", mode="before")(none_if_unknown)


class DailySettingsOut(DailySettings):
    push_configured: bool
    subscriptions: int
    last_sent_date: Optional[str]


class DailyResponse(BaseModel):
    outfit: OutfitOut
    settings: DailySettingsOut


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
    keys: dict[str, str]  # {"p256dh": ..., "auth": ...} as the browser gives them

    @field_validator("endpoint")
    @classmethod
    def _https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("push endpoint must be https")
        return value

    @field_validator("keys")
    @classmethod
    def _keys(cls, value: dict[str, str]) -> dict[str, str]:
        if not value.get("p256dh") or not value.get("auth"):
            raise ValueError("missing p256dh/auth keys")
        return {"p256dh": value["p256dh"], "auth": value["auth"]}


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1000)
