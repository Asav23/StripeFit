"""Personal taste: learned from what the user does, plus what they tell us.

No model is trained. Every thumbs up/down, swap and worn outfit is stored as a StyleSignal; the
profile is recomputed from those on each request. It is used in two places:
  1. the stylist model gets a short summary (liked colours, loved items, past outfits they liked),
  2. the rule-based ranking (fallback + mock mode) scores items by the same signals.
The profile can only reorder candidates that already passed the occasion and weather rules.
"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlmodel import Session, col, delete, select

from app.models import Item, Outfit, StyleSignal, User, as_utc
from app.services import rules

# How much each signal says about an item. Positive = likes it.
SIGNAL_WEIGHTS: dict[str, float] = {"thumbs_up": 2.0, "worn": 1.0, "swap_in": 1.0, "swap_out": -1.0, "thumbs_down": -2.0}
HALF_LIFE_DAYS = 60  # older signals count less: taste changes
LOVED_SCORE = 2.0  # affinity at or above this = a favourite
AVOIDED_SCORE = -2.0  # at or below this = the user keeps rejecting it
FAVOURITE_COLOUR_BONUS = 1.0  # stated favourite colour
AVOID_COLOUR_PENALTY = 4.0  # colour to avoid: strong enough to beat a closer formality match
LEARNED_COLOUR_MIN = 2.0  # total colour affinity before we call it a learned preference
DISPREFERRED_COLOUR_PENALTY = 1.0  # occasion colours to tone down (rules.DISPREFER_COLOURS)
PREFERENCE_WEIGHT = 0.5  # how much taste can outweigh one step of formality in the ranking
MIN_OUTFITS_FOR_LEAN = 2  # liked/worn outfits for an occasion before we say they dress up or down
LEAN_THRESHOLD = 0.5  # formality steps from the occasion's midpoint
MAX_EXAMPLES = 3
MAX_SIGNALS = 1000
NEUTRAL_COLOURS = {"black", "white", "grey", "gray", "navy", "beige", "camel", "denim", "cream", "stone", "unknown"}


# --------------------------------------------------------------------------- recording


def record(session: Session, kind: str, item_ids: Iterable[Optional[int]], *, outfit_id: Optional[int] = None,
           occasion: Optional[str] = None, user_id: int = 1) -> None:
    """Store one signal per item. The caller commits."""
    for item_id in {i for i in item_ids if i}:
        session.add(StyleSignal(user_id=user_id, kind=kind, item_id=item_id, outfit_id=outfit_id, occasion=occasion))


def set_feedback(session: Session, outfit: Outfit, item_ids: list[int], feedback: Optional[str]) -> None:
    """Thumbs replace earlier thumbs for the same outfit, so toggling doesn't double count. The caller commits."""
    session.exec(delete(StyleSignal).where(StyleSignal.outfit_id == outfit.id,  # type: ignore[call-overload]
                                           col(StyleSignal.kind).in_(["thumbs_up", "thumbs_down"])))
    if feedback in ("up", "down"):
        record(session, f"thumbs_{feedback}", item_ids, outfit_id=outfit.id, occasion=outfit.parsed.get("occasion"))


# --------------------------------------------------------------------------- profile


def _decay(created_at: datetime) -> float:
    age_days = max(0.0, (datetime.now(timezone.utc) - as_utc(created_at)).total_seconds() / 86400)  # type: ignore[operator]
    return math.pow(0.5, age_days / HALF_LIFE_DAYS)


def item_affinity(session: Session, user_id: int = 1) -> dict[int, float]:
    """item id -> how much the user likes it (sum of decayed signal weights)."""
    signals = session.exec(select(StyleSignal).where(StyleSignal.user_id == user_id)
                           .order_by(col(StyleSignal.created_at).desc()).limit(MAX_SIGNALS)).all()
    scores: dict[int, float] = defaultdict(float)
    for signal in signals:
        if signal.item_id is not None:
            scores[signal.item_id] += SIGNAL_WEIGHTS.get(signal.kind, 0) * _decay(signal.created_at)
    return {item_id: round(score, 2) for item_id, score in scores.items()}


def _learned_colours(affinity: dict[int, float], items: dict[int, Item]) -> tuple[list[str], list[str]]:
    totals: dict[str, float] = defaultdict(float)
    for item_id, score in affinity.items():
        item = items.get(item_id)
        for colour in (item.colours if item else []):
            if colour not in NEUTRAL_COLOURS:  # neutrals go with everything, so they say little about taste
                totals[colour] += score
    liked = [c for c, v in sorted(totals.items(), key=lambda kv: -kv[1]) if v >= LEARNED_COLOUR_MIN][:3]
    disliked = [c for c, v in sorted(totals.items(), key=lambda kv: kv[1]) if v <= -LEARNED_COLOUR_MIN][:3]
    return liked, disliked


def _liked_outfits(session: Session, occasion: str) -> list[Outfit]:
    recent = session.exec(select(Outfit).order_by(col(Outfit.created_at).desc()).limit(200)).all()
    return [o for o in recent if o.parsed.get("occasion") == occasion and (o.feedback == "up" or o.worn)
            and o.feedback != "down"]


def _outfit_item_ids(outfit: Outfit) -> list[int]:
    ids = [v for k, v in outfit.item_ids.items() if k != "accessory" and v]
    return ids + list(outfit.item_ids.get("accessory") or [])


def _lean(outfits: list[Outfit], items: dict[int, Item], occasion: str) -> Optional[str]:
    """Do they dress up or down for this occasion compared with the default range?"""
    levels = [items[i].formality for o in outfits for i in _outfit_item_ids(o) if i in items and items[i].formality]
    if len(outfits) < MIN_OUTFITS_FOR_LEAN or not levels:
        return None
    low, high = rules.OCCASION_FORMALITY.get(occasion, rules.OCCASION_FORMALITY["other"])
    diff = sum(levels) / len(levels) - (low + high) / 2  # type: ignore[arg-type]
    if diff >= LEAN_THRESHOLD:
        return "dressier than usual"
    if diff <= -LEAN_THRESHOLD:
        return "more relaxed than usual"
    return None


def build(session: Session, occasion: str, user_id: int = 1) -> dict[str, Any]:
    """The full profile for one occasion. `item_affinity` stays server-side (ranking only)."""
    user = session.get(User, user_id) or User(id=user_id)
    items = {i.id: i for i in session.exec(select(Item)).all() if i.id is not None}
    affinity = item_affinity(session, user_id)
    liked_colours, disliked_colours = _learned_colours(affinity, items)
    liked = _liked_outfits(session, occasion)
    examples = [
        {slot: items[i].name for slot, i in o.item_ids.items() if slot != "accessory" and i in items}
        for o in liked[:MAX_EXAMPLES]
    ]
    return {
        "stated": {"favourite_colours": user.favourite_colours or [], "avoid_colours": user.avoid_colours or [],
                   "style_notes": user.style_notes},
        "learned": {
            "liked_colours": liked_colours,
            "disliked_colours": disliked_colours,
            "loved_item_ids": sorted(i for i, s in affinity.items() if s >= LOVED_SCORE),
            "avoided_item_ids": sorted(i for i, s in affinity.items() if s <= AVOIDED_SCORE),
            "lean_for_this_occasion": _lean(liked, items, occasion),
        },
        "liked_outfits_for_this_occasion": examples,
        "item_affinity": affinity,
        "signal_count": sum(1 for _ in affinity),
    }


def for_model(profile: dict[str, Any], candidate_ids: set[int]) -> Optional[dict[str, Any]]:
    """The compact view the stylist model sees. None when we know nothing yet (keeps the prompt short)."""
    learned = profile["learned"]
    view = {
        "favourite_colours": profile["stated"]["favourite_colours"] + learned["liked_colours"],
        "avoid_colours": profile["stated"]["avoid_colours"] + learned["disliked_colours"],
        "notes": profile["stated"]["style_notes"],
        "loved_candidate_ids": [i for i in learned["loved_item_ids"] if i in candidate_ids],
        "rejected_candidate_ids": [i for i in learned["avoided_item_ids"] if i in candidate_ids],
        "dresses": learned["lean_for_this_occasion"],
        "liked_outfits_before": profile["liked_outfits_for_this_occasion"],
    }
    view = {k: v for k, v in view.items() if v}
    return view or None


def preference_score(candidate: dict[str, Any], profile: Optional[dict[str, Any]], requirements: dict[str, Any]) -> float:
    """Higher = the user is more likely to want it. Used by the rule-based ranking."""
    colours = set(candidate.get("colours") or [])
    score = -DISPREFERRED_COLOUR_PENALTY * len(colours & set(requirements.get("disprefer_colours") or []))
    if not profile:
        return score
    stated, learned = profile["stated"], profile["learned"]
    score += profile["item_affinity"].get(candidate["id"], 0.0)
    score += FAVOURITE_COLOUR_BONUS * len(colours & set(stated["favourite_colours"] + learned["liked_colours"]))
    score -= AVOID_COLOUR_PENALTY * len(colours & set(stated["avoid_colours"] + learned["disliked_colours"]))
    return score
