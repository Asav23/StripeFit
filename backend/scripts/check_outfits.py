"""Score the stylist on fixed scenarios: does it dress people right for the event, the weather and their taste?

Each scenario = an occasion, fixed weather, and (optionally) a user taste profile, run against the same
synthetic wardrobe. The checks are code, not opinions (formality range, waterproof in rain, no white at a
wedding, no sportswear at an interview, loved items used ...). Run it before and after every prompt or rules
change and keep the change only if the score doesn't drop. Nothing touches your real wardrobe.

  python scripts/check_outfits.py          # real stylist model (needs OPENROUTER_API_KEY, USE_MOCK_AI=false)
  python scripts/check_outfits.py --mock   # the rule-based picker (what mock mode and the fallback use)
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import create_engine  # noqa: E402

import app.db as db  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import Item  # noqa: E402
from app.services import rules  # noqa: E402
from app.services.outfit_engine import PICK_FIELDS, ai_pick, candidate_dicts  # noqa: E402

# ---- one synthetic wardrobe for every scenario: (id, name, category, colours, formality, warmth, waterproof, material)
WARDROBE = [
    (1, "White Oxford shirt", "top", ["white"], 4, 2, False, "cotton"),
    (2, "Light blue shirt", "top", ["light blue"], 4, 2, False, "cotton"),
    (3, "Grey crew-neck tee", "top", ["grey"], 2, 1, False, "cotton"),
    (4, "Navy knit jumper", "top", ["navy"], 3, 4, False, "wool"),
    (5, "Mustard hoodie", "top", ["mustard"], 1, 3, False, "cotton"),
    (6, "Black going-out top", "top", ["black"], 3, 1, False, "satin"),
    (7, "Red football jersey", "sportswear", ["red"], 1, 1, False, "polyester"),
    (8, "Black training shorts", "sportswear", ["black"], 1, 1, False, "polyester"),
    (9, "Navy suit trousers", "bottom", ["navy"], 5, 2, False, "wool"),
    (10, "Dark wash jeans", "bottom", ["denim"], 2, 3, False, "denim"),
    (11, "Beige chinos", "bottom", ["beige"], 3, 2, False, "cotton"),
    (12, "Charcoal trousers", "bottom", ["charcoal"], 4, 2, False, "wool"),
    (13, "White midi dress", "one_piece", ["white"], 4, 2, False, "cotton"),
    (14, "Emerald satin dress", "one_piece", ["green"], 4, 2, False, "satin"),
    (15, "Black waterproof rain jacket", "outerwear", ["black"], 2, 3, True, "nylon"),
    (16, "Camel wool overcoat", "outerwear", ["camel"], 4, 4, False, "wool"),
    (17, "Navy blazer", "outerwear", ["navy"], 4, 2, False, "wool"),
    (18, "Black puffer jacket", "outerwear", ["black"], 2, 5, True, "nylon"),
    (19, "Black leather Oxford shoes", "shoes", ["black"], 5, None, False, "leather"),
    (20, "White leather trainers", "shoes", ["white"], 2, None, False, "leather"),
    (21, "Brown suede Chelsea boots", "shoes", ["brown"], 3, None, False, "suede"),
    (22, "Running trainers", "shoes", ["grey"], 1, None, False, "mesh"),
    (23, "Black ankle boots", "shoes", ["black"], 3, None, True, "leather"),
    (24, "Burgundy silk tie", "accessory", ["burgundy"], 5, None, None, "silk"),
]
ITEMS = {row[0]: row for row in WARDROBE}
BRIGHT = {"red", "pink", "orange", "yellow", "mustard", "purple", "green", "light blue", "teal", "gold"}


def weather(temp: float, wet: bool = False) -> dict[str, Any]:
    return {"location_name": "Dublin", "time": "", "temperature_c": temp, "temperature_min_c": temp,
            "precipitation_probability": 90 if wet else 5, "precipitation_mm": 2.0 if wet else 0.0, "wind_kmh": 15,
            "weather_code": 63 if wet else 2, "description": "Rain" if wet else "Partly cloudy", "icon": "",
            "is_wet": wet}


# ---- checks: (description, predicate over the picked item rows)
Check = tuple[str, Callable[[list[tuple]], bool]]


def has(pred: Callable[[tuple], bool]) -> Callable[[list[tuple]], bool]:
    return lambda picked: any(pred(i) for i in picked)


def none_(pred: Callable[[tuple], bool]) -> Callable[[list[tuple]], bool]:
    return lambda picked: not any(pred(i) for i in picked)


def main_formality(low: int, high: int) -> Callable[[list[tuple]], bool]:
    return lambda picked: all(low <= (i[4] or low) <= high for i in picked if i[2] in ("top", "bottom", "one_piece"))


SCENARIOS: list[dict[str, Any]] = [
    {"name": "interview, rain, walking", "parsed": {"occasion": "interview", "travel_mode": "walk"}, "weather": weather(9, True),
     "checks": [("smart main pieces (4-5)", main_formality(4, 5)), ("waterproof coat", has(lambda i: i[2] == "outerwear" and i[6])),
                ("no suede in rain", none_(lambda i: i[7] == "suede")), ("no sportswear", none_(lambda i: i[2] == "sportswear"))]},
    {"name": "wedding guest", "parsed": {"occasion": "wedding", "travel_mode": "car"}, "weather": weather(18),
     "checks": [("no white dress", none_(lambda i: i[2] == "one_piece" and "white" in i[3])),
                ("no denim", none_(lambda i: i[7] == "denim")), ("dressy shoes", has(lambda i: i[2] == "shoes" and (i[4] or 0) >= 3))]},
    {"name": "funeral", "parsed": {"occasion": "funeral", "travel_mode": "car"}, "weather": weather(12),
     "checks": [("no bright colours", none_(lambda i: set(i[3]) & BRIGHT)), ("smart (4-5)", main_formality(4, 5))]},
    {"name": "debs", "parsed": {"occasion": "debs", "travel_mode": "car"}, "weather": weather(14),
     "checks": [("formal (4-5)", main_formality(4, 5)), ("no trainers", none_(lambda i: "trainer" in i[1].lower()))]},
    {"name": "football training", "parsed": {"occasion": "sport", "travel_mode": "walk"}, "weather": weather(14),
     "checks": [("sportswear", has(lambda i: i[2] == "sportswear")), ("no leather shoes", none_(lambda i: "Oxford shoes" in i[1]))]},
    {"name": "festival in the rain", "parsed": {"occasion": "festival", "travel_mode": "walk"}, "weather": weather(16, True),
     "checks": [("waterproof coat", has(lambda i: i[2] == "outerwear" and i[6])), ("no suede", none_(lambda i: i[7] == "suede"))]},
    {"name": "night out, 6°C", "parsed": {"occasion": "night_out", "travel_mode": "walk"}, "weather": weather(6),
     "checks": [("a warm coat", has(lambda i: i[2] == "outerwear" and (i[5] or 0) >= 3)), ("no sportswear", none_(lambda i: i[2] == "sportswear"))]},
    {"name": "hot casual day, 24°C", "parsed": {"occasion": "casual", "travel_mode": "walk"}, "weather": weather(24),
     "checks": [("no coat", none_(lambda i: i[2] == "outerwear")), ("light top", none_(lambda i: i[2] == "top" and (i[5] or 0) > 3))]},
    {"name": "uni, 11°C", "parsed": {"occasion": "uni", "travel_mode": "cycle"}, "weather": weather(11),
     "checks": [("a coat", has(lambda i: i[2] == "outerwear")), ("relaxed (1-3)", main_formality(1, 3))]},
    {"name": "match in the stand, 4°C", "parsed": {"occasion": "match", "travel_mode": "bus"}, "weather": weather(4),
     "checks": [("very warm coat", has(lambda i: i[2] == "outerwear" and (i[5] or 0) >= 4))]},
    {"name": "travel day", "parsed": {"occasion": "travel", "travel_mode": "train"}, "weather": weather(15),
     "checks": [("comfortable (1-3)", main_formality(1, 3)), ("no formal shoes", none_(lambda i: "Oxford shoes" in i[1]))]},
    {"name": "presentation", "parsed": {"occasion": "presentation", "travel_mode": "walk"}, "weather": weather(15),
     "checks": [("smart casual (3-4)", main_formality(3, 4)), ("no sportswear", none_(lambda i: i[2] == "sportswear"))]},
    {"name": "taste: loves the navy jumper", "parsed": {"occasion": "casual", "travel_mode": "walk"}, "weather": weather(13),
     "profile": {"loved": [4]}, "checks": [("picks the loved jumper", has(lambda i: i[0] == 4))]},
    {"name": "taste: avoids denim", "parsed": {"occasion": "casual", "travel_mode": "walk"}, "weather": weather(13),
     "profile": {"avoid_colours": ["denim"]}, "checks": [("no denim", none_(lambda i: "denim" in i[3]))]},
]


def make_profile(spec: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not spec:
        return None
    loved = spec.get("loved", [])
    return {
        "stated": {"favourite_colours": [], "avoid_colours": spec.get("avoid_colours", []), "style_notes": None},
        "learned": {"liked_colours": [], "disliked_colours": [], "loved_item_ids": loved, "avoided_item_ids": [],
                    "lean_for_this_occasion": None},
        "liked_outfits_for_this_occasion": [],
        "item_affinity": {i: 4.0 for i in loved},
        "signal_count": len(loved),
    }


def run(scenario: dict[str, Any]) -> tuple[list[str], list[str], bool]:
    wardrobe = [Item(id=i, name=n, category=c, colours=col, formality=f, warmth=w, waterproof=wp, material=m,
                     confirmed=True, owner="me", status="available") for i, n, c, col, f, w, wp, m in WARDROBE]
    parsed = {"occasion_detail": scenario["name"], "destination": None, "datetime_iso": datetime.now().isoformat(),
              "dress_code": None, **scenario["parsed"]}
    filtered = rules.filter_candidates(wardrobe, parsed, scenario["weather"])
    pick, used_fallback = ai_pick(parsed, scenario["weather"], candidate_dicts(filtered.candidates),
                                  filtered.requirements, make_profile(scenario.get("profile")))
    ids = [getattr(pick, f) for f in PICK_FIELDS.values()] + list(pick.accessory_ids)
    picked = [ITEMS[i] for i in ids if i in ITEMS]
    failed = [desc for desc, check in scenario["checks"] if not check(picked)]
    return [p[1] for p in picked], failed, used_fallback


def main() -> None:
    use_mock = "--mock" in sys.argv
    if use_mock:
        settings.USE_MOCK_AI = True
    elif settings.USE_MOCK_AI or not settings.OPENROUTER_API_KEY:
        sys.exit("Set OPENROUTER_API_KEY and USE_MOCK_AI=false in backend/.env first (or pass --mock).")
    db.engine = create_engine("sqlite://")  # AI-call logs go to a throwaway DB, not your real one
    db.init_db()
    print(f"Stylist: {'rule-based (mock)' if use_mock else settings.MODEL_STYLIST}\n")

    total = passed = 0
    for scenario in SCENARIOS:
        names, failed, used_fallback = run(scenario)
        total += len(scenario["checks"])
        passed += len(scenario["checks"]) - len(failed)
        mark = "OK  " if not failed else "MISS"
        note = " (fell back to rules)" if used_fallback and not use_mock else ""
        print(f"{mark} {scenario['name']:32}{note} {', '.join(names)}")
        for desc in failed:
            print(f"       - failed: {desc}")
    print(f"\nScore: {passed}/{total} checks")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
