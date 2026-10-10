"""Create the StripeFit Pro product + one-time €2.99 price (test mode) and write STRIPE_PRICE_ID to .env.

Idempotent: re-running finds the existing price by lookup key instead of creating another.
Run from backend/:  .venv/bin/python scripts/stripe_setup.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe  # noqa: E402

from app.config import ENV_FILE, settings  # noqa: E402
from app.services.stripe_service import CURRENCY, PRICE_CENTS, PRICE_LOOKUP_KEY, PRODUCT_METADATA, PRODUCT_NAME  # noqa: E402


def write_env(key: str, value: str) -> None:
    text = ENV_FILE.read_text()
    line = f"{key}={value}"
    text = re.sub(rf"^{key}=.*$", line, text, flags=re.M) if re.search(rf"^{key}=", text, flags=re.M) else text + f"\n{line}\n"
    ENV_FILE.write_text(text)


def main() -> None:
    if not settings.STRIPE_SECRET_KEY.startswith("sk_test_"):
        sys.exit("STRIPE_SECRET_KEY must be a TEST key (sk_test_...). Add it to backend/.env first.")
    client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)

    existing = client.v1.prices.list(params={"lookup_keys": [PRICE_LOOKUP_KEY], "active": True, "limit": 1}).data
    if existing:
        price = existing[0]
        print(f"Found existing price {price.id}")
    else:
        product = client.v1.products.create(params={
            "name": PRODUCT_NAME,
            "description": "Unlimited wardrobe items plus order-email and Gmail import. One-time purchase.",
            "metadata": {"product": PRODUCT_METADATA},
        })
        price = client.v1.prices.create(params={
            "product": product.id,
            "unit_amount": PRICE_CENTS,
            "currency": CURRENCY,
            "lookup_key": PRICE_LOOKUP_KEY,
        })
        print(f"Created product {product.id} and price {price.id} (€{PRICE_CENTS / 100:.2f} one-time)")

    write_env("STRIPE_PRICE_ID", price.id)
    print("Wrote STRIPE_PRICE_ID to backend/.env")


if __name__ == "__main__":
    main()
