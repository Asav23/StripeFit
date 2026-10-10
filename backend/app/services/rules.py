"""Outfit business rules. Every threshold lives here as a named constant.

filter_candidates() narrows the wardrobe to items that suit the occasion and the weather,
groups them into slots, and records gaps. The AI only ever chooses from its output.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models import Item

# ---- formality (1 gym/lounge, 3 smart casual, 5 black tie): allowed (min, max) per occasion
OCCASION_FORMALITY: dict[str, tuple[int, int]] = {
    "sport": (1, 1), "casual": (1, 3), "uni": (1, 3), "night_out": (2, 4), "date": (2, 4),
    "work": (3, 4), "interview": (4, 5), "wedding": (4, 5), "funeral": (4, 5), "other": (1, 5),
}
# An explicit dress code overrides the occasion's range.
DRESS_CODE_FORMALITY: dict[str, tuple[int, int]] = {
    "black tie": (5, 5), "formal": (4, 5), "cocktail": (4, 5), "business casual": (3, 4),
    "smart casual": (3, 4), "casual": (1, 3),
}
NULL_FORMALITY_OK = {"casual", "uni", "other"}  # unlabelled formality is only risky for dressy occasions
FORMAL_OCCASIONS = {"interview", "wedding", "funeral", "work"}

# ---- weather
WET_RAIN_PROBABILITY = 50  # %
WET_PRECIPITATION_MM = 0.5
EXPOSED_TRAVEL = {"walk", "cycle", "bus", "train", "unknown"}  # you'll be outside for part of the trip
WET_UNSAFE_SHOE_MATERIALS = ("suede", "canvas")
COLD_C, COLD_MIN_OUTER_WARMTH = 10, 3
VERY_COLD_C, VERY_COLD_MIN_OUTER_WARMTH = 5, 4
HOT_C, HOT_MAX_WARMTH = 20, 3  # above HOT_C, drop outerwear/tops with warmth > 3
OUTERWEAR_NEEDED_BELOW_C = 15

# ---- slots
SLOTS = ["top", "bottom", "one_piece", "outerwear", "shoes", "accessory"]
SPORTSWEAR_BOTTOM_WORDS = ("short", "legging", "jogger", "track pant", "tracksuit bottom", "tights", "skort")
MAX_ACCESSORIES = 3
SECOND_HAND_TIP = "borrow one from a friend, or look on Vinted, Depop or in a charity shop"


def is_wet(rain_probability: Optional[float], precipitation_mm: Optional[float]) -> bool:
    return (rain_probability or 0) >= WET_RAIN_PROBABILITY or (precipitation_mm or 0) >= WET_PRECIPITATION_MM


def formality_range(occasion: str, dress_code: Optional[str]) -> tuple[int, int]:
    if dress_code:
        for code, bounds in DRESS_CODE_FORMALITY.items():
            if code in dress_code.lower():
                return bounds
    return OCCASION_FORMALITY.get(occasion, OCCASION_FORMALITY["other"])


def slot_for(item: Item) -> Optional[str]:
    """Which outfit slot an item fills. Sportswear splits into top/bottom by name."""
    if item.category == "sportswear":
        return "bottom" if any(w in item.name.lower() for w in SPORTSWEAR_BOTTOM_WORDS) else "top"
    return item.category if item.category in SLOTS else None


def _material(item: Item) -> str:
    return f"{item.material or ''} {item.name}".lower()


@dataclass
class FilterResult:
    candidates: dict[str, list[Item]]
    requirements: dict[str, Any]
    gaps: list[str] = field(default_factory=list)


def filter_candidates(items: list[Item], parsed: dict[str, Any], weather: Optional[dict[str, Any]]) -> FilterResult:
    """`items` = the user's whole confirmed wardrobe; only available items owned by 'me' are used."""
    occasion = parsed.get("occasion", "other")
    low, high = formality_range(occasion, parsed.get("dress_code"))
    usable = [i for i in items if i.confirmed and i.owner == "me" and i.status == "available" and slot_for(i)]

    def formality_ok(item: Item) -> bool:
        if item.formality is None:
            return occasion in NULL_FORMALITY_OK
        return low <= item.formality <= high

    slots: dict[str, list[Item]] = {s: [] for s in SLOTS}
    for item in usable:
        if formality_ok(item):
            slots[slot_for(item)].append(item)  # type: ignore[index]

    # Sport prefers sportswear; everything else avoids it.
    for slot in ("top", "bottom"):
        sporty = [i for i in slots[slot] if i.category == "sportswear"]
        slots[slot] = (sporty or slots[slot]) if occasion == "sport" else [i for i in slots[slot] if i.category != "sportswear"]

    gaps: list[str] = []
    requirements: dict[str, Any] = {
        "formality_range": [low, high],
        "outerwear_required": False,
        "outerwear_must_be_waterproof": False,
        "avoid": [],
    }
    temp = weather.get("temperature_c") if weather else None
    wet = bool(weather and weather.get("is_wet"))
    exposed = parsed.get("travel_mode", "unknown") in EXPOSED_TRAVEL

    if temp is not None and temp < OUTERWEAR_NEEDED_BELOW_C:
        requirements["outerwear_required"] = True

    if wet and exposed:
        requirements["outerwear_required"] = True
        # Staying dry beats matching formality for a coat, so look at all available outerwear here.
        waterproof = [i for i in usable if slot_for(i) == "outerwear" and i.waterproof is True]
        if waterproof:
            slots["outerwear"] = waterproof
            requirements["outerwear_must_be_waterproof"] = True
        else:
            gaps.append(f"Rain is forecast and you have no waterproof coat: bring an umbrella, or {SECOND_HAND_TIP}.")
        dry_shoes = [i for i in slots["shoes"] if not any(m in _material(i) for m in WET_UNSAFE_SHOE_MATERIALS)]
        if slots["shoes"] and not dry_shoes:
            gaps.append("Your only suitable shoes are suede or canvas and it's wet: they'll get soaked.")
        else:
            slots["shoes"] = dry_shoes
        requirements["avoid"].append("suede or canvas shoes (rain)")

    if temp is not None and temp < COLD_C and slots["outerwear"]:
        min_warmth = VERY_COLD_MIN_OUTER_WARMTH if temp < VERY_COLD_C else COLD_MIN_OUTER_WARMTH
        warm = [i for i in slots["outerwear"] if (i.warmth or 0) >= min_warmth]
        if warm:
            slots["outerwear"] = warm
        else:
            gaps.append(f"It's {round(temp)}°C and none of your suitable coats are very warm: layer up underneath.")

    if temp is not None and temp > HOT_C:
        for slot in ("outerwear", "top"):
            slots[slot] = [i for i in slots[slot] if (i.warmth or 0) <= HOT_MAX_WARMTH]
        requirements["outerwear_required"] = False

    gaps += _slot_gaps(slots, requirements, occasion, items)
    return FilterResult(candidates=slots, requirements=requirements, gaps=gaps)


def _slot_gaps(slots: dict[str, list[Item]], requirements: dict[str, Any], occasion: str, wardrobe: list[Item]) -> list[str]:
    label = occasion.replace("_", " ")
    gaps: list[str] = []

    def unavailable_hint(slot: str) -> str:
        busy = [i for i in wardrobe if i.confirmed and i.owner == "me" and slot_for(i) == slot
                and i.status in ("in_wash", "worn", "unavailable")]
        if busy:
            return f" (your {busy[0].name.lower()} is {busy[0].status.replace('_', ' ')})"
        return ""

    if not slots["shoes"]:
        gaps.append(f"No shoes that suit a {label}{unavailable_hint('shoes')}: {SECOND_HAND_TIP}.")
    has_separates = bool(slots["top"]) and bool(slots["bottom"])
    if not has_separates and not slots["one_piece"]:
        missing = "top" if not slots["top"] else "bottom"
        gaps.append(f"No {missing} that suits a {label}{unavailable_hint(missing)}: {SECOND_HAND_TIP}.")
    if requirements["outerwear_required"] and not slots["outerwear"] and not requirements["outerwear_must_be_waterproof"]:
        if not any("waterproof coat" in g for g in gaps):
            gaps.append(f"You'll want a coat but none suit a {label}{unavailable_hint('outerwear')}.")
    return gaps
