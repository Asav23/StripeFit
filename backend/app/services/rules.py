"""Outfit business rules. Every threshold lives here as a named constant.

filter_candidates() narrows the wardrobe to items that suit the occasion and the weather,
groups them into slots, and records gaps. The AI only ever chooses from its output.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.models import Item

# ---- formality (1 gym/lounge, 3 smart casual, 5 black tie): allowed (min, max) per occasion
OCCASION_FORMALITY: dict[str, tuple[int, int]] = {
    "sport": (1, 1), "casual": (1, 3), "uni": (1, 3), "night_out": (2, 4), "date": (2, 4),
    "work": (3, 4), "interview": (4, 5), "wedding": (4, 5), "funeral": (4, 5),
    "debs": (4, 5), "society": (2, 3), "match": (1, 3), "festival": (1, 2), "travel": (1, 3), "presentation": (3, 4),
    "other": (1, 5),
}
OCCASIONS = list(OCCASION_FORMALITY)  # the parser, schemas and UI all use this list
# An explicit dress code overrides the occasion's range.
DRESS_CODE_FORMALITY: dict[str, tuple[int, int]] = {
    "black tie": (5, 5), "formal": (4, 5), "cocktail": (4, 5), "business casual": (3, 4),
    "smart casual": (3, 4), "casual": (1, 3),
}
# Unlabelled formality is only risky for dressy occasions.
NULL_FORMALITY_OK = {"casual", "uni", "festival", "travel", "match", "other"}
FORMAL_OCCASIONS = {"interview", "wedding", "funeral", "work", "debs", "presentation"}  # get an accessory (e.g. a tie)
OUTERWEAR_FORMALITY_SLACK = 1  # a coat goes over the outfit, so it may be one step off the range
OCCASION_PHRASES = {
    "uni": "uni", "casual": "a casual day", "night_out": "a night out", "date": "a date", "interview": "an interview",
    "work": "work", "wedding": "a wedding", "funeral": "a funeral", "sport": "sport", "debs": "the debs",
    "society": "a society event", "match": "the match", "festival": "a festival", "travel": "a travel day",
    "presentation": "a presentation", "other": "this plan",
}

# ---- event style guide: what each occasion expects. Sent to the stylist model with every pick,
# so its choices (and explanations) follow the same rules for everyone. Keep each line short.
EVENT_STYLE_GUIDE: dict[str, dict[str, list[str]]] = {
    "casual": {
        "expect": ["Comfortable, put-together everyday clothes", "Layers you can add or remove through the day"],
        "avoid": ["Gym clothes, unless it's a lazy day by choice"],
        "combos": ["Jeans or chinos + plain tee or knit + clean trainers", "A neutral base with one colour accent"],
    },
    "uni": {
        "expect": ["Comfortable for sitting in lectures and walking across campus", "A layer for cold lecture halls"],
        "avoid": ["Shoes you can't walk in all day"],
        "combos": ["Jeans + hoodie or knit + trainers", "Chinos + overshirt + trainers"],
    },
    "night_out": {
        "expect": ["One step dressier than daytime", "You'll queue outside and walk between venues, so take a jacket"],
        "avoid": ["Sportswear", "Shoes you can't stand in for hours"],
        "combos": ["Dark jeans + going-out top or shirt + boots", "A dark base with one statement piece"],
    },
    "date": {
        "expect": ["Smart casual: a bit of effort without looking overdressed"],
        "avoid": ["Sportswear", "Anything worn-out or creased"],
        "combos": ["Dark jeans or chinos + shirt or nice knit + clean shoes"],
    },
    "interview": {
        "expect": ["One step dressier than the company's everyday wear", "Clean, polished shoes", "Muted colours"],
        "avoid": ["Loud patterns or logos", "Trainers unless the company is very casual", "Sportswear"],
        "combos": ["Suit trousers + shirt + blazer + leather shoes", "Navy, grey, white and black work together"],
    },
    "work": {
        "expect": ["Neat and practical for a full day"],
        "avoid": ["Sportswear", "Anything too casual for the office"],
        "combos": ["Chinos or trousers + shirt or knit + leather shoes or clean trainers"],
    },
    "wedding": {
        "expect": ["Dressier than work", "Shoes you can stand and dance in for hours"],
        "avoid": ["White, cream or ivory as the main colour (that's for the couple)", "Denim", "Sportswear"],
        "combos": ["Suit + shirt + tie + leather shoes", "Dress + smart shoes + a light layer for the evening"],
    },
    "funeral": {
        "expect": ["Dark, muted colours: black, navy, charcoal, grey", "Simple and respectful"],
        "avoid": ["Bright colours", "Logos and loud patterns", "Denim"],
        "combos": ["Dark suit or trousers + plain shirt + dark shoes"],
    },
    "debs": {
        "expect": ["Formal: a suit or tux, or a formal dress", "Shoes you can dance in"],
        "avoid": ["Denim", "Trainers", "Sportswear"],
        "combos": ["Suit + shirt + tie or bow tie + leather shoes", "Formal dress + heels or smart flats"],
    },
    "society": {
        "expect": ["Relaxed but tidy; it depends on the society, so stay in the middle"],
        "avoid": ["Gym clothes"],
        "combos": ["Jeans + shirt or nice top + clean trainers"],
    },
    "match": {
        "expect": ["Warm and comfortable for standing outside for hours", "Team colours if you have them"],
        "avoid": ["Smart shoes that can't handle a wet stand"],
        "combos": ["Jeans + hoodie or jersey + warm jacket + trainers or boots"],
    },
    "festival": {
        "expect": ["Practical for a long day outside, standing and walking", "Layers for the evening chill"],
        "avoid": ["New or white shoes", "Anything precious"],
        "combos": ["Shorts or jeans + tee + waterproof jacket + boots or old trainers"],
    },
    "travel": {
        "expect": ["Comfort first for sitting for hours", "Layers for planes, trains and the destination's weather"],
        "avoid": ["Tight or restrictive clothes", "Shoes that are hard to take off at security"],
        "combos": ["Joggers or soft jeans + tee + hoodie + slip-on trainers"],
    },
    "presentation": {
        "expect": ["Smart casual or smarter, so you look confident in front of a room"],
        "avoid": ["Sportswear", "Anything you'll fiddle with"],
        "combos": ["Chinos or trousers + shirt or blazer + clean shoes"],
    },
    "sport": {
        "expect": ["Sportswear that suits the activity", "A layer for before and after"],
        "avoid": ["Cotton jeans", "Smart shoes"],
        "combos": ["Sports top + shorts or leggings + trainers + a light jacket"],
    },
    "other": {"expect": ["Versatile, smart casual"], "avoid": [], "combos": []},
}
# Colours kept out of the main pieces (top / one-piece) per occasion. Enforced in code, not just suggested.
AVOID_MAIN_COLOURS: dict[str, set[str]] = {"wedding": {"white", "cream", "ivory", "off-white", "ecru"}}
# Colours ranked lower per occasion (soft: still used if nothing else suits).
DISPREFER_COLOURS: dict[str, set[str]] = {
    "funeral": {"red", "pink", "orange", "yellow", "mustard", "purple", "green", "light blue", "teal", "gold"},
    "interview": {"pink", "orange", "yellow", "mustard"},
}
COLOUR_RULES = [
    "At most one bold colour or pattern per outfit; everything else neutral.",
    "Neutrals (black, white, grey, navy, beige, camel, denim) go with everything.",
    "Match the formality of the shoes to the top.",
    "Keep leather colours consistent (shoes, belt, bag) when the occasion is dressy.",
]

# ---- event length: weather is checked across the whole event, not just the start hour
DEFAULT_DURATION_HOURS: dict[str, float] = {
    "night_out": 5, "wedding": 10, "debs": 8, "festival": 10, "casual": 8, "uni": 8, "work": 8, "travel": 6,
    "match": 3, "date": 3, "funeral": 3, "society": 3, "interview": 2, "sport": 2, "presentation": 2, "other": 3,
}
MAX_DURATION_HOURS = 16


def event_hours(parsed: dict[str, Any]) -> float:
    hours = parsed.get("duration_hours") or DEFAULT_DURATION_HOURS.get(parsed.get("occasion", "other"), 3)
    return max(1.0, min(float(hours), MAX_DURATION_HOURS))


def style_brief(occasion: str) -> dict[str, Any]:
    """The style guide entry + colour rules for one occasion, as sent to the model."""
    guide = EVENT_STYLE_GUIDE.get(occasion, EVENT_STYLE_GUIDE["other"])
    return {"occasion": occasion, **guide, "colour_rules": COLOUR_RULES}


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
SECOND_HAND_TIP = "borrow from a friend, or look on Vinted, Depop or in a charity shop"
BUSY_STATUS_TEXT = {"in_wash": "in the wash", "worn": "waiting for the wash", "unavailable": "marked unavailable"}


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
        slack = OUTERWEAR_FORMALITY_SLACK if slot_for(item) == "outerwear" else 0
        return low - slack <= item.formality <= high + slack

    slots: dict[str, list[Item]] = {s: [] for s in SLOTS}
    for item in usable:
        if formality_ok(item):
            slots[slot_for(item)].append(item)  # type: ignore[index]

    # Sport prefers sportswear; everything else avoids it.
    for slot in ("top", "bottom"):
        sporty = [i for i in slots[slot] if i.category == "sportswear"]
        slots[slot] = (sporty or slots[slot]) if occasion == "sport" else [i for i in slots[slot] if i.category != "sportswear"]

    gaps: list[str] = []
    banned_colours = AVOID_MAIN_COLOURS.get(occasion, set())
    if banned_colours:
        for slot in ("top", "one_piece"):
            kept = [i for i in slots[slot] if not set(i.colours or []) & banned_colours]
            if slot == "one_piece" or kept:  # a white shirt stays only if it's the sole top (it sits under a jacket)
                slots[slot] = kept
    requirements: dict[str, Any] = {
        "formality_range": [low, high],
        "outerwear_required": False,
        "outerwear_must_be_waterproof": False,
        "avoid": [],
        "prefer_warmth": None,  # "cooler" | "warmer": a tie-breaker for ranking
        "avoid_main_colours": sorted(banned_colours),
        "disprefer_colours": sorted(DISPREFER_COLOURS.get(occasion, set())),
    }
    # The coldest hour of the event decides coats and layers ("temperature_min_c" covers the whole event).
    temp = weather.get("temperature_min_c", weather.get("temperature_c")) if weather else None
    wet = bool(weather and weather.get("is_wet"))
    exposed = parsed.get("travel_mode", "unknown") in EXPOSED_TRAVEL

    if temp is not None and temp < OUTERWEAR_NEEDED_BELOW_C:
        requirements["outerwear_required"] = True
    if temp is not None and (temp < COLD_C or temp > HOT_C):
        requirements["prefer_warmth"] = "warmer" if temp < COLD_C else "cooler"

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

    gaps += _slot_gaps(slots, requirements, occasion, items, formality_ok)
    return FilterResult(candidates=slots, requirements=requirements, gaps=gaps)


def _slot_gaps(slots: dict[str, list[Item]], requirements: dict[str, Any], occasion: str, wardrobe: list[Item],
               formality_ok: Callable[[Item], bool]) -> list[str]:
    label = OCCASION_PHRASES.get(occasion, "this plan")
    gaps: list[str] = []

    def unavailable_hint(slot: str) -> str:
        """Point out a suitable item that's only missing because it's in the wash / lent out."""
        busy = [i for i in wardrobe if i.confirmed and i.owner == "me" and slot_for(i) == slot
                and i.status in BUSY_STATUS_TEXT and formality_ok(i)]
        if busy:
            return f" (your {busy[0].name.lower()} {'are' if busy[0].name.lower().endswith('s') else 'is'} {BUSY_STATUS_TEXT[busy[0].status]})"
        return ""

    if not slots["shoes"]:
        gaps.append(f"No shoes that suit {label}{unavailable_hint('shoes')}: {SECOND_HAND_TIP}.")
    has_separates = bool(slots["top"]) and bool(slots["bottom"])
    if not has_separates and not slots["one_piece"]:
        missing = "top" if not slots["top"] else "bottom"
        gaps.append(f"No {missing} that suits {label}{unavailable_hint(missing)}: {SECOND_HAND_TIP}.")
    if requirements["outerwear_required"] and not slots["outerwear"] and not requirements["outerwear_must_be_waterproof"]:
        if not any("waterproof coat" in g for g in gaps):
            gaps.append(f"You'll want a coat, but none suit {label}{unavailable_hint('outerwear')}.")
    return gaps
