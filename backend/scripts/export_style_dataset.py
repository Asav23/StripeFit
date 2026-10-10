"""Export outfits + what the user did with them as JSONL: the dataset for any future taste model.

One row per outfit: the occasion context, the weather, each picked item's features, and the outcome
(thumbs, worn, swaps). Free text (the request, the destination) is left out by default because it can
be personal; pass --include-text to keep it. Nothing leaves this computer: the file is written to
backend/exports/ (gitignored). Get the user's consent before sharing it anywhere.

  python scripts/export_style_dataset.py [--include-text] [--out path.jsonl]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, col, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.models import Item, Outfit, StyleSignal  # noqa: E402

EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"
ITEM_FIELDS = ("category", "colours", "formality", "warmth", "waterproof", "material")
CONTEXT_FIELDS = ("occasion", "travel_mode", "dress_code", "setting", "activity", "duration_hours", "datetime_iso")
WEATHER_FIELDS = ("temperature_c", "temperature_min_c", "precipitation_probability_max", "is_wet", "description")


def main() -> None:
    include_text = "--include-text" in sys.argv
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else EXPORT_DIR / "style_dataset.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    with Session(engine) as session:
        items = {i.id: i for i in session.exec(select(Item)).all()}
        signals: dict[int, list[StyleSignal]] = defaultdict(list)
        for signal in session.exec(select(StyleSignal)).all():
            if signal.outfit_id:
                signals[signal.outfit_id].append(signal)
        outfits = session.exec(select(Outfit).order_by(col(Outfit.created_at))).all()
        with out.open("w", encoding="utf-8") as f:
            for outfit in outfits:
                f.write(json.dumps(_row(outfit, items, signals[outfit.id], include_text)) + "\n")  # type: ignore[index]
    print(f"Wrote {len(outfits)} outfits to {out}")


def _row(outfit: Outfit, items: dict, signals: list[StyleSignal], include_text: bool) -> dict:
    picked = []
    for slot, value in outfit.item_ids.items():
        for item_id in (value if isinstance(value, list) else [value]):
            item = items.get(item_id)
            if item:
                picked.append({"slot": slot, "item_id": item_id, **{f: getattr(item, f) for f in ITEM_FIELDS}})
    row = {
        "outfit_id": outfit.id,
        "kind": outfit.kind,
        "created_at": outfit.created_at.isoformat(),
        "context": {f: outfit.parsed.get(f) for f in CONTEXT_FIELDS},
        "weather": {f: (outfit.weather or {}).get(f) for f in WEATHER_FIELDS} if outfit.weather else None,
        "items": picked,
        "used_fallback": outfit.used_fallback,
        "outcome": {
            "feedback": outfit.feedback,
            "worn": outfit.worn,
            "swapped_out": [s.item_id for s in signals if s.kind == "swap_out"],
            "swapped_in": [s.item_id for s in signals if s.kind == "swap_in"],
        },
    }
    if include_text:
        row["request_text"] = outfit.request_text
        row["context"]["destination"] = outfit.parsed.get("destination")
    return row


if __name__ == "__main__":
    main()
