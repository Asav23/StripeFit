"""Run each configured model (primary + fallbacks) on real calls and check it returns valid JSON.

Needs OPENROUTER_API_KEY in backend/.env. Costs well under €0.05 in total.
  .venv/bin/python scripts/check_models.py
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import prompts  # noqa: E402
from app.ai.client import AIError, call_json, image_part  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.schemas import ClothingLabels, OrderExtraction, OutfitPick, ParsedRequest  # noqa: E402
from app.services.images import make_placeholder  # noqa: E402
from app.config import UPLOAD_DIR  # noqa: E402

PICK_REQUEST = {"occasion": "interview", "destination": "Grand Canal Dock", "travel_mode": "walk"}
PICK_WEATHER = {"temperature_c": 11, "description": "Rain", "is_wet": True, "precipitation_probability": 80}
PICK_RULES = {"formality_range": [4, 5], "outerwear_required": True, "outerwear_must_be_waterproof": True}
PICK_CANDIDATES = [
    {"id": 1, "slot": "top", "name": "White Oxford shirt", "colours": ["white"], "formality": 4, "days_since_worn": 6},
    {"id": 6, "slot": "bottom", "name": "Navy suit trousers", "colours": ["navy"], "formality": 5, "days_since_worn": 30},
    {"id": 10, "slot": "outerwear", "name": "Black waterproof rain jacket", "colours": ["black"], "waterproof": True},
    {"id": 14, "slot": "shoes", "name": "Black leather Oxford shoes", "colours": ["black"], "formality": 5},
    {"id": 18, "slot": "accessory", "name": "Burgundy silk tie", "colours": ["burgundy"], "formality": 5},
]
SAMPLE_EMAIL = Path(__file__).resolve().parent.parent / "samples" / "emails" / "01_zalando_order.eml"


def run(task: str, model: str, messages: list, schema: type) -> None:
    started = time.perf_counter()
    try:
        result = call_json(task, model, [], messages, schema, max_tokens=800)  # no fallbacks: test this model alone
        print(f"  OK   {model:45} {time.perf_counter() - started:5.1f}s  {str(result.model_dump())[:90]}")
    except AIError as exc:
        print(f"  FAIL {model:45} {time.perf_counter() - started:5.1f}s  {exc.kind}: {exc.detail[:80]}")


def main() -> None:
    if settings.USE_MOCK_AI or not settings.OPENROUTER_API_KEY:
        sys.exit("Set OPENROUTER_API_KEY and USE_MOCK_AI=false in backend/.env first.")
    init_db()
    tile, _ = make_placeholder("Navy wool blazer", "outerwear", ["navy"])
    now = datetime.now(settings.tz)
    from app.services.email_extract import read_upload
    from app.services.redact import redact
    email_text = redact(read_upload(SAMPLE_EMAIL.name, SAMPLE_EMAIL.read_bytes()).text or "")

    for kind in ("vision", "fast", "stylist"):
        primary, fallbacks = settings.models_for(kind)
        print(f"\n[{kind}]")
        for model in [primary, *fallbacks]:
            if kind == "vision":
                run("check_vision", model, prompts.label_messages(image_part(UPLOAD_DIR / tile)), ClothingLabels)
            elif kind == "fast":
                run("check_parse", model, prompts.parse_messages("Interview tomorrow 10am in Grand Canal Dock, walking", now), ParsedRequest)
                run("check_extract", model, prompts.extract_messages(email_text, {"sender_domain": "zalando.ie"}), OrderExtraction)
            else:
                run("check_pick", model, prompts.pick_messages(PICK_REQUEST, PICK_WEATHER, PICK_CANDIDATES, PICK_RULES), OutfitPick)


if __name__ == "__main__":
    main()
