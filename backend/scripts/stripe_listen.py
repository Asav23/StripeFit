"""Forward Stripe test-mode webhooks to the local API and keep STRIPE_WEBHOOK_SECRET in .env up to date.

Works on Windows, macOS and Linux. Uses STRIPE_SECRET_KEY from backend/.env, so `stripe login`
isn't needed. Needs the Stripe CLI (Windows: `winget install Stripe.StripeCli`; macOS:
`brew install stripe/stripe-cli/stripe`).
Run from backend/:  python scripts/stripe_listen.py     (leave it running)
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_file import ENV_PATH, read_env_value, write_env_value  # noqa: E402

FORWARD_TO = "127.0.0.1:8000/api/stripe/webhook"


def main() -> None:
    if not ENV_PATH.exists():
        sys.exit("backend/.env is missing. Copy .env.example to .env first.")
    key = read_env_value("STRIPE_SECRET_KEY")
    if not key.startswith("sk_test_"):
        sys.exit("STRIPE_SECRET_KEY in backend/.env must be a test key (sk_test_...).")
    stripe = shutil.which("stripe")
    if stripe is None:
        sys.exit("The Stripe CLI isn't on PATH. Windows: winget install Stripe.StripeCli (then open a new terminal).")

    secret = subprocess.run([stripe, "listen", "--api-key", key, "--print-secret"],
                            capture_output=True, text=True, check=False).stdout.strip()
    if not secret.startswith("whsec_"):
        sys.exit("The Stripe CLI didn't return a webhook secret. Check the key is a valid test key.")
    write_env_value("STRIPE_WEBHOOK_SECRET", secret)
    print("Wrote STRIPE_WEBHOOK_SECRET to backend/.env (the API reloads automatically).")
    print(f"Forwarding checkout.session.completed to {FORWARD_TO}. Leave this running; Ctrl+C to stop.")
    try:
        subprocess.run([stripe, "listen", "--api-key", key, "--forward-to", FORWARD_TO,
                        "--events", "checkout.session.completed"], check=False)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
