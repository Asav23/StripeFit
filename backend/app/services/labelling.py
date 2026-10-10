"""Photo -> pending wardrobe item, via the vision model."""

import logging

from PIL import Image
from sqlmodel import Session

from app.ai import prompts
from app.ai.client import AIError, call_json, image_part
from app.config import UPLOAD_DIR, settings
from app.models import Item
from app.schemas import ClothingLabels
from app.services import images

log = logging.getLogger("stripefit.labelling")

AI_DOWN_NOTE = "AI labelling was unavailable, so please fill in the details yourself."


class NotClothing(Exception):
    pass


def label_image(image_path: str, phash: str) -> ClothingLabels:
    model, fallbacks = settings.models_for("vision")
    return call_json(
        "label_photo", model, fallbacks, prompts.label_messages(image_part(UPLOAD_DIR / image_path)),
        ClothingLabels, mock_input=phash, max_tokens=500,
    )


def ingest_photo(session: Session, img: Image.Image) -> Item:
    """Save, label and queue for review. Raises NotClothing (files are cleaned up)."""
    image_path, thumb_path, phash = images.save_photo(img)
    try:
        labels = label_image(image_path, phash)
    except AIError as exc:
        # Deterministic fallback: keep the photo, ask the user to fill in the labels.
        log.warning("Labelling failed, queueing unlabelled item: %s", exc)
        labels = ClothingLabels(name="New item", confidence=0.0, notes=AI_DOWN_NOTE)

    if not labels.is_clothing:
        images.delete_files(image_path, thumb_path)
        raise NotClothing(labels.notes or "That doesn't look like clothing.")

    item = Item(
        name=labels.name,
        image_path=image_path,
        thumb_path=thumb_path,
        image_hash=phash,
        has_real_photo=True,
        category=labels.category,
        colours=labels.colours,
        formality=labels.formality,
        warmth=labels.warmth,
        waterproof=labels.waterproof,
        material=labels.material,
        confidence=labels.confidence,
        notes=labels.notes,
        source="photo",
        confirmed=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
