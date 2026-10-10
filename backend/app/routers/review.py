"""Review queue: nothing the AI produces becomes a wardrobe item until the user confirms it."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.db import get_session
from app.errors import api_error, not_found
from app.models import Item
from app.schemas import ConfirmRequest, DuplicateOut, ReviewItemOut
from app.services import dedupe, images
from app.services.limits import ensure_capacity
from app.services.serialize import item_out

router = APIRouter(prefix="/api/review", tags=["review"])

LOW_CONFIDENCE = 0.6
OWNER_PROMPTS = {
    "child": "This looks like a child's size. Is this yours?",
    "other": "This looks like a gift for someone else. Is this yours?",
    "unknown": "Is this yours?",
}


def _missing_fields(item: Item) -> list[str]:
    missing = []
    if item.category == "unknown":
        missing.append("category")
    if item.colours == ["unknown"] or not item.colours:
        missing.append("colours")
    if item.formality is None:
        missing.append("formality")
    if item.warmth is None and item.category not in ("shoes", "accessory"):
        missing.append("warmth")
    if item.waterproof is None and item.category == "outerwear":
        missing.append("waterproof")
    return missing


def _review_out(session: Session, item: Item) -> ReviewItemOut:
    duplicate = dedupe.find_duplicate(session, item)
    prompt = OWNER_PROMPTS.get(item.owner)
    if prompt is None and not item.has_real_photo:
        prompt = "No photo yet. Add one so it's easier to spot in your wardrobe."
    return ReviewItemOut(
        **item_out(item).model_dump(),
        duplicate=DuplicateOut(item=item_out(duplicate.item), level=duplicate.level, reason=duplicate.reason)  # type: ignore[arg-type]
        if duplicate else None,
        missing_fields=_missing_fields(item),
        low_confidence=item.confidence is not None and item.confidence < LOW_CONFIDENCE,
        prompt=prompt,
    )


def _pending(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None or item.confirmed or item.dismissed:
        raise not_found("Review item")
    return item


@router.get("", response_model=list[ReviewItemOut])
def list_review(session: Session = Depends(get_session)) -> list[ReviewItemOut]:
    items = session.exec(
        select(Item).where(Item.confirmed == False, Item.dismissed == False).order_by(col(Item.created_at))  # noqa: E712
    ).all()
    return [_review_out(session, i) for i in items]


@router.post("/{item_id}/confirm")
def confirm(item_id: int, body: ConfirmRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    item = _pending(session, item_id)
    edits = body.model_dump(exclude_unset=True, exclude={"duplicate_decision", "merge_target_id"})
    for field, value in edits.items():
        setattr(item, field, value)
    if item.category == "unknown":
        raise api_error(422, "category_required", "Pick a category before confirming.")
    if not item.name.strip():
        raise api_error(422, "name_required", "Give this item a name before confirming.")

    if body.duplicate_decision == "merge":
        target = session.get(Item, body.merge_target_id) if body.merge_target_id else None
        if target is None or not target.confirmed:
            raise api_error(404, "merge_target_missing", "The item to merge into no longer exists.", "Choose “Keep both” instead.")
        merged = dedupe.merge_into(session, item, target)
        return {"item": item_out(merged), "merged": True}

    if body.duplicate_decision is None:
        duplicate = dedupe.find_duplicate(session, item)
        if duplicate:
            session.rollback()  # don't keep unconfirmed edits half-applied
            raise api_error(
                409,
                "possible_duplicate",
                f"Looks like your {duplicate.item.name.lower()}. Same item?",
                "Merge them, or keep both.",
                duplicate=DuplicateOut(item=item_out(duplicate.item), level=duplicate.level,  # type: ignore[arg-type]
                                       reason=duplicate.reason).model_dump(mode="json"),
            )

    ensure_capacity(session)
    item.confirmed = True
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"item": item_out(item), "merged": False}


@router.post("/{item_id}/reject", status_code=204)
def reject(item_id: int, session: Session = Depends(get_session)) -> None:
    item = _pending(session, item_id)
    if item.source_ref:  # from an order: keep a tombstone so re-importing the email doesn't bring it back
        item.dismissed = True
        session.add(item)
    else:
        images.delete_files(item.image_path, item.thumb_path)
        session.delete(item)
    session.commit()
