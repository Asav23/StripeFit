#!/usr/bin/env bash
# Forward Stripe test-mode webhooks to the local API and keep STRIPE_WEBHOOK_SECRET in .env up to date.
# Uses STRIPE_SECRET_KEY from backend/.env, so no `stripe login` is needed.
# Run from backend/:  ./scripts/stripe_listen.sh
set -euo pipefail
cd "$(dirname "$0")/.."

KEY=$(grep -E '^STRIPE_SECRET_KEY=' .env | cut -d= -f2- | tr -d '[:space:]')
if [[ "$KEY" != sk_test_* ]]; then
  echo "STRIPE_SECRET_KEY in backend/.env must be a test key (sk_test_...)." >&2
  exit 1
fi

SECRET=$(stripe listen --api-key "$KEY" --print-secret)
if grep -qE '^STRIPE_WEBHOOK_SECRET=' .env; then
  sed -i '' -E "s|^STRIPE_WEBHOOK_SECRET=.*|STRIPE_WEBHOOK_SECRET=${SECRET}|" .env
else
  echo "STRIPE_WEBHOOK_SECRET=${SECRET}" >> .env
fi
echo "Wrote STRIPE_WEBHOOK_SECRET to backend/.env (the API reloads automatically)."

exec stripe listen --api-key "$KEY" --forward-to localhost:8000/api/stripe/webhook --events checkout.session.completed
