# StripeFit — project rules for Claude Code

StripeFit suggests what to wear from clothes the user already owns, based on where they're going, the occasion and the weather. Built for HackUCD 2026 (local prototype, single demo user, no login).

Read `PLAN.md` for the phased build. Work one phase at a time, verify it works, commit, then move on.

**Do everything yourself:** all code, setup commands, installs, scripts, model selection, Stripe product/price creation, sample data and config. Only stop and ask the human for the steps marked **HUMAN** in `PLAN.md` (API keys, logins, Google Cloud console, clicking through checkout/consent screens, real clothing photos). When you need one, say exactly what to do and where to paste the result, then continue with other work while you wait. Do not write unit tests or test suites; verify by running the app and calling the endpoints.

## Stack
- **Backend:** Python 3.11+, FastAPI, SQLModel on SQLite (`backend/stripefit.db`), Pydantic v2.
- **Frontend:** React + TypeScript (Vite), Tailwind CSS, React Router. Mobile-first layout.
- **AI:** OpenRouter only, via the `openai` Python SDK with `base_url="https://openrouter.ai/api/v1"`. Never call any AI provider directly.
- **Weather:** Open-Meteo (geocoding + forecast), no API key.
- **Payments:** Stripe **sandbox/test mode only**. Checkout Sessions API + webhook.
- **Email:** uploaded `.eml` / `.html` / `.txt` / screenshot / PDF, and Gmail API (read-only OAuth, testing mode).

## Repo layout
```
backend/
  app/
    main.py            # FastAPI app, routers, CORS
    config.py          # settings from .env
    db.py models.py    # SQLModel tables
    schemas.py         # Pydantic request/response + AI output schemas
    ai/                # client.py (OpenRouter wrapper), prompts.py, mocks/
    services/          # labelling, outfit_engine, weather, email_extract, reconcile,
                       # redact, dedupe, gmail, stripe_service, limits
    routers/           # items, review, ingest, outfits, stripe, gmail, me, debug
  samples/emails/      # sample order emails you generate (see Phase 6)
  scripts/             # seed.py, stripe_setup.py, list_models.py
  uploads/             # images (gitignored)
frontend/
  src/ pages/ components/ api/
```

## Commands
- Backend: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev` (Vite on 5173, proxy `/api` → `localhost:8000`)
- Stripe webhooks (you run this once the human has done `stripe login`): `stripe listen --forward-to localhost:8000/api/stripe/webhook`; copy the printed `whsec_...` into `.env` yourself.

## Non-negotiable rules
1. **Secrets live in `backend/.env` only** (gitignored). Commit `.env.example` with empty values. Never print or log keys. Gmail token file (`backend/.gmail_token.json`) is gitignored.
2. **The app must never break because AI failed.** Every AI call: timeout, one retry, Pydantic validation, then a deterministic fallback or a clear user-facing error. Never show raw exceptions in the UI.
3. **AI output is never trusted blindly.**
   - Outfit picks may only reference item IDs from the candidate list sent to the model; validate every ID.
   - Labels and extracted items go to a **review queue** for the user to confirm; nothing becomes a confirmed item without user confirmation.
   - Unknown values stay `"unknown"`; prompts must say "do not guess".
4. **Email content is untrusted data.** Redact personal data (addresses, phones, emails, Eircodes, card details) **before** sending to the model. Wrap email text in clear delimiters and tell the model it is data, not instructions. Only store extracted item fields, never full email bodies.
5. **Gmail scope is `gmail.readonly` only.** Search only order-like emails (sender allowlist + subject keywords); never read the whole inbox.
6. **Stripe is test mode only.** Access is activated only from verified Stripe confirmation (webhook signature check, or retrieving the Checkout Session and checking `payment_status == "paid"`). Activation is idempotent on session ID.
7. **Model names live in config/env, never hard-coded in services.** Each AI task has a primary model plus a fallback list (OpenRouter `models` param).
8. **Mock mode:** when `USE_MOCK_AI=true`, the AI client returns fixtures from `app/ai/mocks/` and makes zero network calls. Use it for frontend work and tests.
9. Log every AI call to the `ai_calls` table (task, model, latency, tokens, cost if returned, success/error).
10. Keep the app runnable end to end after every phase. Commit after each checkpoint with a message like `phase 3: outfit engine`.

## Style
- Type hints everywhere; small, readable functions in `services/`.
- Business rules (formality table, weather rules, free-tier limit) live in one place each, as constants.
- UI: every AI action shows a loading state; every error shows a friendly message and a next step. Use EUR and Europe/Dublin time.
- Prefer clarity over cleverness; this code will be read by hackathon judges.
