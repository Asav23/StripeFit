"""Duplicate detection when confirming a review item, and merging.

Levels (strongest first):
  definite: exact source_ref match (same retailer|order|item|size) beyond the ordered quantity
  likely:   the same photo again, or same category + overlapping colour + a very similar photo
  possible: same category + same retailer + similar name
Units of the same order line (e.g. 2 identical T-shirts) are never duplicates of each other.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from sqlmodel import Session, select

from app.models import Item
from app.services import images

HASH_DISTANCE_THRESHOLD = 8  # of 64 bits: similar photo of the same category and colour
SAME_PHOTO_DISTANCE = 4  # near-identical image: a re-upload of the same photo
NAME_SIMILARITY_THRESHOLD = 0.6
LEVEL_RANK = {"definite": 0, "likely": 1, "possible": 2}
MERGEABLE_FIELDS = ("category", "colours", "formality", "warmth", "waterproof", "material", "retailer", "size",
                    "price", "currency", "source_ref", "order_qty")


@dataclass
class Duplicate:
    item: Item
    level: str
    reason: str


def normalise_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", name.lower())).strip()


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalise_name(a), normalise_name(b)).ratio()


def _colours_overlap(a: list[str], b: list[str]) -> bool:
    known_a, known_b = set(a) - {"unknown"}, set(b) - {"unknown"}
    return not known_a or not known_b or bool(known_a & known_b)


def find_duplicate(session: Session, item: Item) -> Optional[Duplicate]:
    others = [
        o for o in session.exec(select(Item).where(Item.confirmed == True, Item.id != item.id)).all()  # noqa: E712
        if o.status != "returned"
    ]
    found: list[tuple[int, int, Duplicate]] = []

    if item.source_ref:
        same_line = [o for o in others if o.source_ref == item.source_ref]
        if len(same_line) >= (item.order_qty or 1):
            found.append((0, 0, Duplicate(same_line[0], "definite", "This exact item from the same order is already in your wardrobe.")))
        others = [o for o in others if o.source_ref != item.source_ref]  # sibling units aren't duplicates

    for other in others:
        distance = images.hash_distance(item.image_hash, other.image_hash)
        if distance is not None and distance <= SAME_PHOTO_DISTANCE:  # the same photo, whatever the labels say
            found.append((1, distance, Duplicate(other, "likely", "This looks like the same photo.")))
            continue
        if other.category != item.category or not _colours_overlap(item.colours, other.colours):
            continue
        if distance is not None and distance <= HASH_DISTANCE_THRESHOLD:
            found.append((1, distance, Duplicate(other, "likely", "Very similar photo, same category and colour.")))
        elif (item.retailer and other.retailer and normalise_name(item.retailer) == normalise_name(other.retailer)
              and name_similarity(item.name, other.name) >= NAME_SIMILARITY_THRESHOLD):
            found.append((2, 0, Duplicate(other, "possible", f"Same shop ({other.retailer}) and a similar name.")))

    return min(found, key=lambda f: (f[0], f[1]))[2] if found else None


def _is_blank(value: object) -> bool:
    return value is None or value == "unknown" or value == ["unknown"]


def merge_into(session: Session, pending: Item, target: Item) -> Item:
    """Fold a pending item into an existing one: keep the real photo and fill missing labels.

    The target's existing values win (the user already confirmed them); we only fill gaps.
    """
    if pending.has_real_photo and not target.has_real_photo:
        images.delete_files(target.image_path, target.thumb_path)
        target.image_path, target.thumb_path = pending.image_path, pending.thumb_path
        target.image_hash, target.has_real_photo = pending.image_hash, True
        pending.image_path = pending.thumb_path = None  # now owned by target
    for field in MERGEABLE_FIELDS:
        if _is_blank(getattr(target, field)) and not _is_blank(getattr(pending, field)):
            setattr(target, field, getattr(pending, field))
    images.delete_files(pending.image_path, pending.thumb_path)
    session.delete(pending)
    session.add(target)
    session.commit()
    session.refresh(target)
    return target
