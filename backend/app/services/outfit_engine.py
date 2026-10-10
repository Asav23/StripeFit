"""The outfit engine: parse request -> weather -> rules filter -> AI pick -> validate -> fallback.

The AI never sees the whole wardrobe and never gets the last word: every ID it returns is
checked against the candidate list, and if it can't produce a valid outfit in two tries
we use a deterministic rule-based pick instead.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlmodel import Session, col, select

from app.ai import prompts
from app.ai.client import AIError, call_json
from app.config import settings
from app.errors import api_error
from app.models import Item, Outfit, as_utc, utcnow
from app.schemas import OutfitOut, OutfitPick, OutfitSlotOut, ParsedRequest, PlanResponse, WeatherOut
from app.services import rules, style_profile, weather as weather_service
from app.services.request_rules import parse_request_rules
from app.services.serialize import item_out

log = logging.getLogger("stripefit.outfits")

MAX_REQUEST_CHARS = 500
MAX_EXPLANATION_WORDS = 60
PICK_FIELDS = {"top": "top_id", "bottom": "bottom_id", "one_piece": "one_piece_id", "outerwear": "outerwear_id",
               "shoes": "shoes_id"}
UNKNOWN_FORMALITY_DISTANCE = 1.5
NEVER_WORN_DAYS = 10_000


# --------------------------------------------------------------------------- 1. parse


def parse_request(text: str, now: datetime) -> tuple[ParsedRequest, bool]:
    """Returns (parsed, used_fallback)."""
    model, fallbacks = settings.models_for("fast")
    try:
        parsed = call_json(
            "parse_request", model, fallbacks, prompts.parse_messages(text, now), ParsedRequest,
            mock_input={"text": text, "now": now.isoformat()}, max_tokens=400,
        )
        return parsed, False
    except AIError as exc:
        log.warning("Parse fell back to keyword rules: %s", exc)
        return parse_request_rules(text, now), True


def _when(parsed: ParsedRequest) -> datetime:
    when = datetime.fromisoformat(parsed.datetime_iso)
    return when.replace(tzinfo=settings.tz) if when.tzinfo is None else when


# --------------------------------------------------------------------------- 4. candidates + AI pick


def _days_since_worn(item: Item) -> Optional[int]:
    last = as_utc(item.last_worn)
    return None if last is None else max(0, (datetime.now(timezone.utc) - last).days)


def candidate_dicts(candidates: dict[str, list[Item]]) -> list[dict[str, Any]]:
    """Only these fields are ever sent to the model."""
    return [
        {
            "id": item.id, "slot": slot, "name": item.name, "category": item.category, "colours": item.colours,
            "formality": item.formality, "warmth": item.warmth, "waterproof": item.waterproof,
            "material": item.material, "days_since_worn": _days_since_worn(item),
        }
        for slot, items in candidates.items()
        for item in items
    ]


def _rank(options: list[dict[str, Any]], requirements: dict[str, Any],
          profile: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Best first: formality close to the occasion midpoint, adjusted by the user's taste (favourite items and
    colours, occasion colours to tone down), then suits the temperature, then least recently worn."""
    low, high = requirements["formality_range"]
    midpoint = (low + high) / 2
    prefer = requirements.get("prefer_warmth")

    def key(c: dict[str, Any]) -> tuple[float, int, int]:
        distance = abs(c["formality"] - midpoint) if c["formality"] is not None else UNKNOWN_FORMALITY_DISTANCE
        taste = style_profile.preference_score(c, profile, requirements)
        warmth = c["warmth"] if c["warmth"] is not None else 3
        warmth_penalty = warmth if prefer == "cooler" else -warmth if prefer == "warmer" else 0
        days = c["days_since_worn"] if c["days_since_worn"] is not None else NEVER_WORN_DAYS
        return distance - style_profile.PREFERENCE_WEIGHT * taste, warmth_penalty, -days

    return sorted(options, key=key)


def rule_based_pick(candidates: list[dict[str, Any]], parsed: dict[str, Any], requirements: dict[str, Any],
                    profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Deterministic pick per slot. Returns OutfitPick-shaped dict (without explanation)."""
    by_slot = {s: _rank([c for c in candidates if c["slot"] == s], requirements, profile) for s in rules.SLOTS}
    pick: dict[str, Any] = {f: None for f in PICK_FIELDS.values()}
    if by_slot["top"] and by_slot["bottom"]:
        pick["top_id"], pick["bottom_id"] = by_slot["top"][0]["id"], by_slot["bottom"][0]["id"]
    elif by_slot["one_piece"]:
        pick["one_piece_id"] = by_slot["one_piece"][0]["id"]
    else:  # incomplete wardrobe: still show what we have
        pick["top_id"] = by_slot["top"][0]["id"] if by_slot["top"] else None
        pick["bottom_id"] = by_slot["bottom"][0]["id"] if by_slot["bottom"] else None
    if by_slot["shoes"]:
        pick["shoes_id"] = by_slot["shoes"][0]["id"]
    if requirements.get("outerwear_required") and by_slot["outerwear"]:
        pick["outerwear_id"] = by_slot["outerwear"][0]["id"]
    accessory = by_slot["accessory"][:1] if parsed.get("occasion") in rules.FORMAL_OCCASIONS else []
    pick["accessory_ids"] = [a["id"] for a in accessory]
    return pick


def validate_pick(pick: OutfitPick, candidates: list[dict[str, Any]], requirements: dict[str, Any]) -> list[str]:
    """Every problem with an AI pick, as short messages the model can act on. Empty = valid."""
    ids_by_slot = {s: {c["id"] for c in candidates if c["slot"] == s} for s in rules.SLOTS}
    errors: list[str] = []
    for slot, field_name in PICK_FIELDS.items():
        value = getattr(pick, field_name)
        if value is not None and value not in ids_by_slot[slot]:
            errors.append(f"{field_name}={value} is not one of the {slot} candidates {sorted(ids_by_slot[slot])}")
    bad_acc = [a for a in pick.accessory_ids if a not in ids_by_slot["accessory"]]
    if bad_acc:
        errors.append(f"accessory_ids {bad_acc} are not accessory candidates")
    if len(set(pick.accessory_ids)) != len(pick.accessory_ids) or len(pick.accessory_ids) > rules.MAX_ACCESSORIES:
        errors.append(f"accessory_ids must be unique and at most {rules.MAX_ACCESSORIES}")

    if pick.one_piece_id and (pick.top_id or pick.bottom_id):
        errors.append("use either one_piece_id or top_id + bottom_id, not both")
    can_separates = bool(ids_by_slot["top"]) and bool(ids_by_slot["bottom"])
    if not pick.one_piece_id and not (pick.top_id and pick.bottom_id) and (can_separates or ids_by_slot["one_piece"]):
        errors.append("the outfit needs a one_piece_id, or both a top_id and a bottom_id")
    if ids_by_slot["shoes"] and not pick.shoes_id:
        errors.append("shoes_id is required")
    if requirements.get("outerwear_required") and ids_by_slot["outerwear"] and not pick.outerwear_id:
        errors.append("outerwear_id is required (weather)")
    if not pick.explanation.strip():
        errors.append("explanation is empty")
    return errors


def ai_pick(parsed: dict[str, Any], weather: Optional[dict[str, Any]], candidates: list[dict[str, Any]],
            requirements: dict[str, Any], profile: Optional[dict[str, Any]] = None) -> tuple[OutfitPick, bool]:
    """Returns (pick, used_fallback)."""
    model, fallbacks = settings.models_for("stylist")
    brief = rules.style_brief(parsed.get("occasion", "other"))
    taste = style_profile.for_model(profile, {c["id"] for c in candidates}) if profile else None
    messages = prompts.pick_messages(parsed, weather, candidates, requirements, brief, taste)
    mock_input = {"parsed": parsed, "weather": weather, "candidates": candidates, "requirements": requirements,
                  "profile": profile}
    for attempt in range(2):
        try:
            pick = call_json("pick_outfit", model, fallbacks, messages, OutfitPick, mock_input=mock_input, max_tokens=500)
        except AIError as exc:
            log.warning("Outfit pick AI failed: %s", exc)
            break
        errors = validate_pick(pick, candidates, requirements)
        if not errors:
            return pick, False
        log.warning("Outfit pick invalid (attempt %d): %s", attempt + 1, errors)
        messages = messages + [
            {"role": "assistant", "content": pick.model_dump_json()},
            {"role": "user", "content": "That outfit breaks the rules: " + "; ".join(errors) + ". Fix it and reply with JSON only."},
        ]
    fallback = OutfitPick(**rule_based_pick(candidates, parsed, requirements, profile), explanation="")
    return fallback, True


def _trim_words(text: str, limit: int = MAX_EXPLANATION_WORDS) -> str:
    words = text.split()
    return text.strip() if len(words) <= limit else " ".join(words[:limit]) + "…"


def template_explanation(parsed: dict[str, Any], weather: Optional[dict[str, Any]], names: list[str]) -> str:
    occasion = parsed.get("occasion", "other").replace("_", " ")
    if weather:
        weather_bit = f"{round(weather['temperature_c'])}°C, {weather['description'].lower()}"
        if weather.get("is_wet"):
            weather_bit += ", so we kept you dry"
    else:
        weather_bit = "no forecast, so we ignored the weather"
    picked = ", ".join(names) if names else "nothing suitable yet"
    return f"Rule-based pick for your {occasion} ({weather_bit}): {picked}. Chosen for the right formality and least recently worn."


# --------------------------------------------------------------------------- main entry points


def _wardrobe(session: Session) -> list[Item]:
    return list(session.exec(select(Item).where(Item.confirmed == True)).all())  # noqa: E712


def usable_wardrobe(session: Session) -> list[Item]:
    """The confirmed wardrobe, or a friendly 409 if there's nothing to pick from."""
    wardrobe = _wardrobe(session)
    mine = [i for i in wardrobe if i.owner == "me" and i.status != "returned"]
    if not mine:
        raise api_error(409, "empty_wardrobe", "Your wardrobe is empty, so there's nothing to pick from yet.",
                        "Add your first items on the Add tab.")
    if not any(i.status == "available" for i in mine):
        raise api_error(409, "nothing_available", "Everything you own is worn, in the wash or unavailable.",
                        "Tap “Laundry done” on the Wardrobe tab when your clothes are clean.")
    return wardrobe


def plan_outfit(session: Session, request_text: str) -> PlanResponse:
    text = request_text.strip()
    if not text:
        raise api_error(422, "empty_request", "Tell us where you're going first.",
                        "Try: “Interview tomorrow 10am in Grand Canal Dock, walking”.")
    if len(text) > MAX_REQUEST_CHARS:
        raise api_error(422, "request_too_long", f"That's a bit long. Keep it under {MAX_REQUEST_CHARS} characters.",
                        "Just say where, when and how you're getting there.")

    wardrobe = usable_wardrobe(session)
    now = datetime.now(settings.tz)
    parsed, parse_fallback = parse_request(text, now)
    if parsed.needs_clarification:
        return PlanResponse(clarification=parsed.needs_clarification)

    notices: list[str] = []
    if parse_fallback:
        notices.append("The AI couldn't read your note, so we matched keywords instead. Check the occasion below.")
    outfit = build_outfit(session, wardrobe, text, parsed, parse_fallback=parse_fallback, notices=notices)
    return PlanResponse(outfit=outfit_out(session, outfit))


def _without(candidates: dict[str, list[Item]], exclude_ids: set[int]) -> dict[str, list[Item]]:
    """Drop excluded items, but never empty a slot (an outfit beats a perfect rotation)."""
    out = {}
    for slot, items in candidates.items():
        kept = [i for i in items if i.id not in exclude_ids]
        out[slot] = kept or items
    return out


def build_outfit(session: Session, wardrobe: list[Item], text: str, parsed: ParsedRequest, *,
                 parse_fallback: bool = False, notices: Optional[list[str]] = None, kind: str = "plan",
                 for_date: Optional[str] = None, exclude_ids: Iterable[int] = ()) -> Outfit:
    """weather (whole event) -> rules -> user's taste -> AI pick -> validate -> save. Shared by plans and daily fits."""
    notices = list(notices or [])
    parsed_dict = parsed.model_dump()
    weather_obj, weather_notices = weather_service.forecast_for(parsed.destination, _when(parsed),
                                                                rules.event_hours(parsed_dict))
    notices += weather_notices
    weather = weather_obj.model_dump() if weather_obj else None

    filtered = rules.filter_candidates(wardrobe, parsed_dict, weather)
    pool = _without(filtered.candidates, set(exclude_ids)) if exclude_ids else filtered.candidates
    candidates = candidate_dicts(pool)
    profile = style_profile.build(session, parsed.occasion)
    pick, used_fallback = ai_pick(parsed_dict, weather, candidates, filtered.requirements, profile)

    item_ids = {slot: getattr(pick, f) for slot, f in PICK_FIELDS.items()}
    item_ids["accessory"] = pick.accessory_ids
    names = [c["name"].lower() for c in candidates if c["id"] in _all_ids(item_ids)]
    explanation = template_explanation(parsed_dict, weather, names) if used_fallback else _trim_words(pick.explanation)

    outfit = Outfit(
        request_text=text,
        parsed={**parsed_dict, "parse_fallback": parse_fallback},
        weather=weather,
        item_ids=item_ids,
        explanation=explanation,
        gaps=filtered.gaps,
        notices=notices,
        used_fallback=used_fallback,
        kind=kind,
        for_date=for_date,
    )
    session.add(outfit)
    session.commit()
    session.refresh(outfit)
    return outfit


def _all_ids(item_ids: dict[str, Any]) -> list[int]:
    ids = [v for k, v in item_ids.items() if k != "accessory" and v]
    return ids + list(item_ids.get("accessory") or [])


def swap_slot(session: Session, outfit: Outfit, slot: str) -> Outfit:
    """Replace one slot with the next-best candidate (cycles through the options)."""
    filtered = rules.filter_candidates(_wardrobe(session), outfit.parsed, outfit.weather)
    profile = style_profile.build(session, outfit.parsed.get("occasion", "other"))
    options = _rank([c for c in candidate_dicts(filtered.candidates) if c["slot"] == slot],
                    {**filtered.requirements}, profile)
    current_value = outfit.item_ids.get(slot)
    current = (current_value[0] if current_value else None) if slot == "accessory" else current_value
    option_ids = [o["id"] for o in options]
    alternatives = [i for i in option_ids if i != current]
    if not alternatives:
        raise api_error(409, "no_alternative", f"There's no other {slot.replace('_', ' ')} that suits this plan.",
                        "Add more items, or run the laundry.")
    if current in option_ids:  # take the next one after the current item, wrapping around
        next_id = option_ids[(option_ids.index(current) + 1) % len(option_ids)]
    else:
        next_id = alternatives[0]

    item_ids = dict(outfit.item_ids)  # reassign so SQLAlchemy sees the JSON change
    item_ids[slot] = [next_id] if slot == "accessory" else next_id
    outfit.item_ids = item_ids
    outfit.worn = False
    occasion = outfit.parsed.get("occasion")
    style_profile.record(session, "swap_out", [current], outfit_id=outfit.id, occasion=occasion)
    style_profile.record(session, "swap_in", [next_id], outfit_id=outfit.id, occasion=occasion)
    session.add(outfit)
    session.commit()
    session.refresh(outfit)
    return outfit


def wear_outfit(session: Session, outfit: Outfit) -> Outfit:
    now = utcnow()
    for item in session.exec(select(Item).where(col(Item.id).in_(_all_ids(outfit.item_ids)))).all():
        item.status = "worn"
        item.last_worn = now
        session.add(item)
    outfit.worn = True
    style_profile.record(session, "worn", _all_ids(outfit.item_ids), outfit_id=outfit.id,
                         occasion=outfit.parsed.get("occasion"))
    session.add(outfit)
    session.commit()
    session.refresh(outfit)
    return outfit


def outfit_out(session: Session, outfit: Outfit) -> OutfitOut:
    slots: list[OutfitSlotOut] = []
    for slot in ("top", "bottom", "one_piece", "outerwear", "shoes"):
        item_id = outfit.item_ids.get(slot)
        item = session.get(Item, item_id) if item_id else None
        if item:
            slots.append(OutfitSlotOut(slot=slot, item=item_out(item)))  # type: ignore[arg-type]
    for item_id in outfit.item_ids.get("accessory") or []:
        item = session.get(Item, item_id)
        if item:
            slots.append(OutfitSlotOut(slot="accessory", item=item_out(item)))
    return OutfitOut(
        id=outfit.id,  # type: ignore[arg-type]
        request_text=outfit.request_text,
        parsed=outfit.parsed,
        weather=WeatherOut.model_validate(outfit.weather) if outfit.weather else None,
        slots=slots,
        explanation=outfit.explanation,
        gaps=outfit.gaps,
        notices=outfit.notices,
        used_fallback=outfit.used_fallback,
        feedback=outfit.feedback,
        worn=outfit.worn,
        created_at=outfit.created_at,
        kind=outfit.kind,
        for_date=outfit.for_date,
    )


def set_feedback(session: Session, outfit: Outfit, feedback: Optional[str]) -> Outfit:
    outfit.feedback = feedback
    style_profile.set_feedback(session, outfit, _all_ids(outfit.item_ids), feedback)
    session.add(outfit)
    session.commit()
    session.refresh(outfit)
    return outfit
