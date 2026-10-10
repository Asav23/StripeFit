"""Wardrobe CRUD, status changes and laundry."""

from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, col, select

from app.db import get_session
from app.errors import api_error, not_found
from app.models import Item, utcnow
from app.schemas import IdList, ItemCreate, ItemOut, ItemUpdate, StatusUpdate
from app.services import images, laundry
from app.services.limits import ensure_capacity
from app.services.serialize import item_out

router = APIRouter(prefix="/api/items", tags=["items"])


def _get(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise not_found()
    return item


@router.get("", response_model=list[ItemOut])
def list_items(
    status: Optional[str] = None,
    category: Optional[str] = None,
    confirmed: bool = True,
    session: Session = Depends(get_session),
) -> list[ItemOut]:
    query = select(Item).where(Item.confirmed == confirmed)
    if status:
        query = query.where(Item.status == status)
    else:
        query = query.where(Item.status != "returned")  # returned items only show when asked for
    if category:
        query = query.where(Item.category == category)
    items = session.exec(query.order_by(col(Item.created_at).desc())).all()
    return [item_out(i) for i in items]


@router.post("", response_model=ItemOut, status_code=201)
def create_item(body: ItemCreate, session: Session = Depends(get_session)) -> ItemOut:
    """Manually add an item (no AI). Goes straight into the wardrobe."""
    if body.category == "unknown":
        raise api_error(422, "category_required", "Pick a category for this item.")
    ensure_capacity(session)
    image_path, thumb_path = images.make_placeholder(body.name, body.category, body.colours)
    item = Item(**body.model_dump(), image_path=image_path, thumb_path=thumb_path, confirmed=True, source="manual")
    session.add(item)
    session.commit()
    session.refresh(item)
    return item_out(item)


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(item_id: int, body: ItemUpdate, session: Session = Depends(get_session)) -> ItemOut:
    item = _get(session, item_id)
    changes = body.model_dump(exclude_unset=True)
    if item.confirmed and changes.get("category") == "unknown":
        raise api_error(422, "category_required", "A wardrobe item needs a category.")
    for field, value in changes.items():
        setattr(item, field, value)
    if changes.get("status") == "worn":
        item.last_worn = utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item_out(item)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, session: Session = Depends(get_session)) -> None:
    item = _get(session, item_id)
    images.delete_files(item.image_path, item.thumb_path)
    session.delete(item)
    session.commit()


@router.post("/bulk-delete")
def bulk_delete(body: IdList, session: Session = Depends(get_session)) -> dict[str, int]:
    items = session.exec(select(Item).where(col(Item.id).in_(body.ids))).all()
    for item in items:
        images.delete_files(item.image_path, item.thumb_path)
        session.delete(item)
    session.commit()
    return {"deleted": len(items)}


@router.post("/{item_id}/status", response_model=ItemOut)
def set_status(item_id: int, body: StatusUpdate, session: Session = Depends(get_session)) -> ItemOut:
    item = _get(session, item_id)
    item.status = body.status
    if body.status == "worn":
        item.last_worn = utcnow()
    if body.status == "in_wash":
        laundry.mark_washed(item)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item_out(item)


def _move_status(session: Session, from_status: str, to_status: str) -> int:
    items = session.exec(select(Item).where(Item.confirmed == True, Item.status == from_status)).all()  # noqa: E712
    for item in items:
        item.status = to_status
        if to_status == "in_wash":
            laundry.mark_washed(item)
        session.add(item)
    session.commit()
    return len(items)


@router.post("/wash-worn")
def wash_worn(session: Session = Depends(get_session)) -> dict[str, int]:
    """'Put worn items in the wash': worn -> in_wash."""
    return {"updated": _move_status(session, "worn", "in_wash")}


@router.post("/laundry-done")
def laundry_done(session: Session = Depends(get_session)) -> dict[str, int]:
    """All in_wash -> available."""
    return {"updated": _move_status(session, "in_wash", "available")}


@router.post("/{item_id}/photo", response_model=ItemOut)
async def replace_photo(item_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)) -> ItemOut:
    """Attach a real photo to an item (e.g. one imported from an order email). No AI involved."""
    item = _get(session, item_id)
    try:
        img = images.open_photo(await file.read())
    except images.ImageRejected as exc:
        raise api_error(422, "bad_image", str(exc))
    old = (item.image_path, item.thumb_path)
    item.image_path, item.thumb_path, item.image_hash = images.save_photo(img)
    item.has_real_photo = True
    session.add(item)
    session.commit()
    session.refresh(item)
    images.delete_files(*old)
    return item_out(item)
