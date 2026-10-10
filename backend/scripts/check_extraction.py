"""Run every sample order email through the REAL extraction model and compare with the expected answers.

The expected answers are the mock fixtures in app/ai/mocks/extract_order*.json, which encode what a
correct extraction of each sample looks like. Nothing is written to the wardrobe; AI calls are logged
to the AI log as usual. Costs a few cents.

  python scripts/check_extraction.py          # real models (needs OPENROUTER_API_KEY, USE_MOCK_AI=false)
  python scripts/check_extraction.py --mock   # check the script itself against the fixtures (should all pass)

If an email shows DIFF, tune EXTRACT_SYSTEM in app/ai/prompts.py and re-run.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai import mocks  # noqa: E402
from app.ai.client import AIError  # noqa: E402
from app.config import MOCKS_DIR, settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.schemas import OrderExtraction  # noqa: E402
from app.services import email_extract  # noqa: E402
from app.services.redact import redact  # noqa: E402

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples" / "emails"


def expected_for(doc: email_extract.EmailDoc) -> OrderExtraction:
    """The fixture the mock would return for this email: the answer we want from a real model."""
    if doc.image is not None:
        data, key = json.loads((MOCKS_DIR / "extract_order_image.json").read_text(encoding="utf-8")), doc.ref
    else:
        data = json.loads((MOCKS_DIR / "extract_order.json").read_text(encoding="utf-8"))
        key = redact(doc.text or "")[: email_extract.MAX_TEXT_CHARS]
    return OrderExtraction.model_validate(mocks._select(data, key))


def item_facts(extraction: OrderExtraction) -> Counter:
    """What must match per item. Names and prices may be worded differently, so they aren't compared."""
    return Counter(
        (i.category, i.is_clothing, i.likely_for, i.exchange_role, i.quantity, (i.size or "").replace(" ", "").upper(),
         i.colours == ["unknown"])
        for i in extraction.items
    )


def compare(got: OrderExtraction, want: OrderExtraction) -> list[str]:
    problems = []
    if got.email_type != want.email_type:
        problems.append(f"email_type {got.email_type!r}, expected {want.email_type!r}")
    if (got.order_id or "") != (want.order_id or ""):
        problems.append(f"order_id {got.order_id!r}, expected {want.order_id!r}")
    if len(got.items) != len(want.items):
        problems.append(f"{len(got.items)} items, expected {len(want.items)}")
    missing, extra = item_facts(want) - item_facts(got), item_facts(got) - item_facts(want)
    fields = "(category, is_clothing, likely_for, exchange_role, quantity, size, colour unknown)"
    if missing:
        problems.append(f"missing items {fields}: {sorted(missing.elements())}")
    if extra:
        problems.append(f"unexpected items: {sorted(extra.elements())}")
    return problems


def main() -> None:
    use_mock = "--mock" in sys.argv
    if use_mock:
        settings.USE_MOCK_AI = True
    elif settings.USE_MOCK_AI or not settings.OPENROUTER_API_KEY:
        sys.exit("Set OPENROUTER_API_KEY and USE_MOCK_AI=false in backend/.env first (or pass --mock).")
    init_db()
    print(f"Fast model: {settings.MODEL_FAST} · vision model: {settings.MODEL_VISION} · mock: {use_mock}\n")

    passed = failed = skipped = 0
    for path in sorted(SAMPLES_DIR.glob("*")):
        if path.suffix.lower() not in email_extract.TEXT_TYPES | email_extract.IMAGE_TYPES:
            continue
        doc = email_extract.read_upload(path.name, path.read_bytes())
        reason = email_extract.prefilter(doc)
        if reason:
            skipped += 1
            print(f"SKIP  {path.name:34} pre-filter: {reason} (no AI call)")
            continue
        try:
            got = email_extract.extract(doc)
        except AIError as exc:
            failed += 1
            print(f"FAIL  {path.name:34} AI error: {exc.kind}")
            continue
        problems = compare(got, expected_for(doc))
        if problems:
            failed += 1
            print(f"DIFF  {path.name:34} " + "\n" + "\n".join(f"        - {p}" for p in problems))
        else:
            passed += 1
            print(f"OK    {path.name:34} {got.email_type}, {len(got.items)} item(s)")

    print(f"\n{passed} match · {failed} differ · {skipped} skipped by the pre-filter")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
