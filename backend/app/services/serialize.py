"""Turn table rows into API response objects."""

from app.models import Item
from app.schemas import ItemOut
from app.services.images import url_for


def item_out(item: Item) -> ItemOut:
    data = item.model_dump()
    data["image_url"] = url_for(item.image_path)
    data["thumb_url"] = url_for(item.thumb_path or item.image_path)
    return ItemOut.model_validate(data)
