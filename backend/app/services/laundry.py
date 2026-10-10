"""Laundry: what wearing an outfit does to each item, and when to tell the user to put a wash on.

Not everything needs washing after one wear: tops do, jeans get a few wears, coats and shoes never
go in the wash from wearing (rules.WEARS_BEFORE_WASH). The day planner uses advice() to warn the
night before when clean clothes are running low, or when the right item for tomorrow is in the wash.
"""

from datetime import datetime
from typing import Any, Iterable, Optional

from app.models import Item
from app.services import rules


def record_wear(item: Item, when: datetime) -> None:
    """One wear. The item stays available until it has had its wears, then it waits for the wash."""
    item.last_worn = when
    item.wears_since_wash = (item.wears_since_wash or 0) + 1
    limit = rules.wears_before_wash(item.category)
    if limit is not None and item.wears_since_wash >= limit:
        item.status = "worn"


def mark_washed(item: Item) -> None:
    item.wears_since_wash = 0


def _mine(wardrobe: Iterable[Item]) -> list[Item]:
    return [i for i in wardrobe if i.confirmed and i.owner == "me" and i.status != "returned"]


def _plural(n: int, word: str) -> str:
    return f"{n} clean {word}{'' if n == 1 else 's'}"


def advice(wardrobe: list[Item], picked_ids: set[int], parsed: dict[str, Any], weather: Optional[dict[str, Any]],
           day_label: str) -> list[str]:
    """Short laundry tips for the planned day. `wardrobe` = the confirmed wardrobe (any status)."""
    mine = _mine(wardrobe)
    tips: list[str] = []

    # 1. The right item for this day is in the wash (and nothing clean fills that slot).
    as_if_clean = [Item(**{**i.model_dump(), "status": "available"}) for i in mine]
    ideal = rules.filter_candidates(as_if_clean, parsed, weather).candidates
    clean = rules.filter_candidates(mine, parsed, weather).candidates
    busy_ids = {i.id for i in mine if i.status in ("worn", "in_wash")}
    for slot in ("top", "bottom", "one_piece", "shoes", "outerwear"):
        if clean[slot]:
            continue
        waiting = [i for i in ideal[slot] if i.id in busy_ids]
        if waiting:
            tips.append(f"Wash your {waiting[0].name.lower()} tonight if you can: it's the best fit for {day_label}.")

    # 2. Running low on clean basics after this day.
    def clean_left(slot: str) -> int:
        return sum(1 for i in mine if i.status == "available" and rules.slot_for(i) == slot and i.id not in picked_ids
                   and i.category != "sportswear")

    tops, bottoms = clean_left("top"), clean_left("bottom")
    if tops < rules.LOW_CLEAN_TOPS:
        tips.append(f"After {day_label} you'll have {_plural(tops, 'top')} left. Put a wash on.")
    elif bottoms < rules.LOW_CLEAN_BOTTOMS:
        tips.append(f"After {day_label} you'll have {_plural(bottoms, 'pair')} of trousers or jeans left. Put a wash on.")

    # 3. A big pile is waiting.
    pile = sum(1 for i in mine if i.status == "worn")
    if pile >= rules.LAUNDRY_PILE_WARNING and not any("Put a wash on" in t for t in tips):
        tips.append(f"{pile} items are waiting for the wash. Put a load on when you can.")
    return tips
