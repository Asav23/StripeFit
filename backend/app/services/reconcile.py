"""Turn an extracted order email into wardrobe changes, idempotently.

Every order line has a key `retailer|order_id|normalised_name|size` (Item.source_ref).
  order_confirmation -> one pending item per unit (status on_the_way), skipping what already exists
  dispatch           -> match existing items; create them only if we never saw the confirmation
  delivery           -> matched items become available
  refund/return/cancellation -> matched items become returned (pending ones are dismissed)
  exchange           -> "old" lines returned, "new" lines added
  marketing/other    -> ignored
Re-uploading the same email (or the same order via Gmail) never creates duplicates.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, col, select

from app.models import Item
from app.schemas import ExtractedItem, OrderExtraction
from app.services import images
from app.services.dedupe import name_similarity, normalise_name

FUZZY_NAME_MATCH = 0.5
OWNER_FOR = {"me": "me", "child": "child", "gift": "other", "unknown": "unknown"}
RETURN_TYPES = {"refund", "return", "cancellation"}
IGNORED_TYPES = {"marketing": "marketing email", "other": "not an order email"}


@dataclass
class ReconcileResult:
    created: int = 0
    updated: int = 0
    skipped: list[str] = field(default_factory=list)  # one reason per skipped line


def _norm(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def line_key(retailer: str, order_id: str, name: str, size: Optional[str]) -> str:
    return f"{_norm(retailer)}|{order_id}|{normalise_name(name)}|{_norm(size) or '-'}"


def _order_items(session: Session, retailer: str, order_id: str) -> list[Item]:
    prefix = f"{_norm(retailer)}|{order_id}|"
    return list(session.exec(select(Item).where(col(Item.source_ref).startswith(prefix))).all())


def _match(order_items: list[Item], key: str, line: ExtractedItem) -> list[Item]:
    """All units of the matching order line: exact key first, then the most similar name (same size)."""
    exact = [i for i in order_items if i.source_ref == key]
    if exact:
        return exact
    size = _norm(line.size)
    compatible = [i for i in order_items if not size or not _norm(i.size) or _norm(i.size) == size]
    if not compatible:
        return []
    best = max(compatible, key=lambda i: name_similarity(i.name, line.name))
    if name_similarity(best.name, line.name) < FUZZY_NAME_MATCH:
        return []
    return [i for i in order_items if i.source_ref == best.source_ref]


def _new_item(line: ExtractedItem, key: str, retailer: str, order_id: str, currency: Optional[str],
              source: str, status: str, confidence: float) -> Item:
    downloaded = images.download_image(line.image_url) if line.image_url else None
    if downloaded is not None:
        image_path, thumb_path, phash = images.save_photo(downloaded)
    else:
        image_path, thumb_path = images.make_placeholder(line.name, line.category, line.colours)
        phash = None
    return Item(
        name=line.name[:120],
        image_path=image_path,
        thumb_path=thumb_path,
        image_hash=phash,
        has_real_photo=downloaded is not None,
        category=line.category,
        colours=line.colours,
        owner=OWNER_FOR[line.likely_for],
        status=status,
        confirmed=False,
        confidence=confidence,
        notes=f"From your {retailer} order {order_id}.",
        source=source,
        source_ref=key,
        order_qty=line.quantity,
        retailer=retailer,
        size=line.size,
        price=line.price,
        currency=(currency or "").upper() or None,
    )


def apply(session: Session, extraction: OrderExtraction, retailer: str, order_id: str, source: str) -> ReconcileResult:
    result = ReconcileResult()
    kind = extraction.email_type
    if kind in IGNORED_TYPES:
        result.skipped.append(IGNORED_TYPES[kind])
        return result

    order_items = _order_items(session, retailer, order_id)
    for line in extraction.items:
        if not line.is_clothing:
            result.skipped.append("not clothing")
            continue
        key = line_key(retailer, order_id, line.name, line.size)
        role = "old" if kind in RETURN_TYPES else line.exchange_role if kind == "exchange" else "new"
        if role is None:  # an exchange line we can't place
            result.skipped.append("unclear exchange line")
            continue

        # A confirmation defines the order lines, so it only matches exactly; later emails
        # (dispatch, delivery, refund, exchange) may word the name differently, so they match fuzzily.
        defines_lines = kind == "order_confirmation" or (kind == "exchange" and role == "new")
        matches = [i for i in order_items if i.source_ref == key] if defines_lines else _match(order_items, key, line)

        if role == "old":
            _mark_returned(session, matches, line.quantity, result)
            continue
        if line.status_hint in ("cancelled", "out_of_stock"):
            _mark_returned(session, matches, line.quantity, result, count_skip=False)
            result.skipped.append("cancelled" if line.status_hint == "cancelled" else "out of stock")
            continue

        if kind == "delivery":
            for item in matches:
                if item.status == "on_the_way":
                    item.status = "available"
                    session.add(item)
                    result.updated += 1
        elif kind == "dispatch":
            result.updated += len(matches)  # already known and on the way: nothing to change

        # Create only the units we haven't seen (dismissed/returned ones count, so nothing comes back).
        status = "available" if kind == "delivery" else "on_the_way"
        for _ in range(max(0, line.quantity - len(matches))):
            item = _new_item(line, key, retailer, order_id, extraction.currency, source, status, extraction.confidence)
            session.add(item)
            order_items.append(item)
            result.created += 1
    session.commit()
    return result


def _mark_returned(session: Session, matches: list[Item], quantity: int, result: ReconcileResult,
                   count_skip: bool = True) -> None:
    live = [i for i in matches if i.status != "returned" and not i.dismissed]
    live.sort(key=lambda i: i.confirmed)  # pending units go first
    if not live and count_skip:
        result.skipped.append("no matching item to return")
    for item in live[:quantity]:
        item.status = "returned"
        if not item.confirmed:
            item.dismissed = True  # disappears from the review queue
        session.add(item)
        result.updated += 1
