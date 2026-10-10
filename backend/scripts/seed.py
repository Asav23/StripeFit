"""Seed a demo wardrobe: confirmed items across every category and formality level.

Run from backend/:
  .venv/bin/python scripts/seed.py            # wipe the database and seed fresh
  .venv/bin/python scripts/seed.py --if-empty # only seed when there are no items yet
"""

import shutil
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, select  # noqa: E402

from app.config import DB_PATH, UPLOAD_DIR  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Item, utcnow  # noqa: E402
from app.services.images import make_placeholder  # noqa: E402

# name, category, colours, formality, warmth, waterproof, material, days since worn (None = never)
SEED_ITEMS = [
    ("White Oxford shirt", "top", ["white"], 4, 2, False, "cotton", 6),
    ("Grey crew-neck T-shirt", "top", ["grey"], 1, 1, False, "cotton", 2),
    ("Navy merino jumper", "top", ["navy"], 3, 3, False, "wool", 9),
    ("Black satin going-out top", "top", ["black"], 3, 1, False, "satin", 14),
    ("Dark wash jeans", "bottom", ["blue"], 2, 2, False, "denim", 1),
    ("Navy suit trousers", "bottom", ["navy"], 5, 2, False, "wool", 30),
    ("Beige chinos", "bottom", ["beige"], 3, 2, False, "cotton", None),
    ("Green floral midi dress", "one_piece", ["green", "white"], 4, 1, False, "viscose", 45),
    ("Navy blazer", "outerwear", ["navy"], 4, 2, False, "wool", 30),
    ("Black waterproof rain jacket", "outerwear", ["black"], 2, 3, True, "nylon", 4),
    ("Camel wool overcoat", "outerwear", ["camel"], 4, 4, False, "wool", 60),
    ("Brown suede Chelsea boots", "shoes", ["brown"], 3, None, False, "suede", 8),
    ("White leather trainers", "shoes", ["white"], 2, None, False, "leather", 3),
    ("Black leather Oxford shoes", "shoes", ["black"], 5, None, False, "leather", 30),
    ("Running trainers", "shoes", ["grey", "blue"], 1, None, False, "mesh", 5),
    ("Red football jersey", "sportswear", ["red", "white"], 1, 1, False, "polyester", 7),
    ("Black training shorts", "sportswear", ["black"], 1, 1, False, "polyester", 7),
    ("Burgundy silk tie", "accessory", ["burgundy"], 5, None, None, "silk", 30),
]


def wipe() -> None:
    """Drop and recreate all tables (not the file, so a running API keeps working) and clear images."""
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.drop_all(engine)
    for sub in ("originals", "thumbs", "placeholders"):
        shutil.rmtree(UPLOAD_DIR / sub, ignore_errors=True)


def seed() -> int:
    now = utcnow()
    with Session(engine) as session:
        for i, (name, category, colours, formality, warmth, waterproof, material, worn_days) in enumerate(SEED_ITEMS):
            image_path, thumb_path = make_placeholder(name, category, colours)
            session.add(Item(
                name=name, category=category, colours=colours, formality=formality, warmth=warmth,
                waterproof=waterproof, material=material, image_path=image_path, thumb_path=thumb_path,
                owner="me", status="available", confirmed=True, source="manual",
                last_worn=now - timedelta(days=worn_days) if worn_days is not None else None,
                created_at=now - timedelta(minutes=len(SEED_ITEMS) - i),
            ))
        session.commit()
    return len(SEED_ITEMS)


def main() -> None:
    if "--if-empty" in sys.argv:
        init_db()
        with Session(engine) as session:
            if session.exec(select(Item)).first() is not None:
                print("Items already exist; not seeding.")
                return
    else:
        wipe()
        init_db()
    print(f"Seeded {seed()} items into {DB_PATH.name}")


if __name__ == "__main__":
    main()
