# StripeFit

**Tell StripeFit where you're going; it picks an outfit from clothes you own, that are clean, and that suit the weather.**

Built for HackUCD 2026 as a local prototype: a single demo user, no login. It's a mobile-first web app aimed at students: uni days, nights out, sport, interviews, weddings and work.

| | |
|---|---|
| **Wardrobe** | Photos are labelled by a vision model; nothing joins the wardrobe until you confirm it in **Review** |
| **Plan** | "Interview tomorrow 10am in Grand Canal Dock, walking" → parsed → live Open-Meteo forecast → rules → AI stylist → validated outfit |
| **Laundry** | Worn → in the wash → laundry done. Only clean, available clothes you own are ever picked |
| **Pro (€2.99 one-off)** | Stripe Checkout (test mode). Unlocks unlimited items (free: 20) plus order-email, screenshot and Gmail import |
| **Order import** | Confirmation, dispatch, delivery, refund and exchange emails are reconciled into your wardrobe. Refunds remove items, child sizes and gifts are flagged, and marketing emails are ignored |

## Quick start

```bash
# Backend (Python 3.11+)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # mock AI is on by default, so no keys needed
python scripts/seed.py            # 18 demo items with placeholder images
uvicorn app.main:app --reload --reload-include .env --port 8000
```

```bash
# Frontend (Node 20+), in a second terminal
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api and /uploads to :8000)
```

### On Windows
- Activate the venv with `.venv\Scripts\activate` (PowerShell) or `source .venv/Scripts/activate` (Git Bash).
- If Smart App Control / an Application Control policy blocks SQLAlchemy's compiled extension ("DLL load failed … An Application Control policy has blocked this file"), reinstall it as pure Python:
  ```powershell
  $env:DISABLE_SQLALCHEMY_CEXT="1"; pip install --force-reinstall --no-deps --no-binary sqlalchemy sqlalchemy
  ```
- The frontend proxies to `127.0.0.1:8000`, not `localhost`, because Docker Desktop and WSL can also listen on port 8000 over IPv6.
- Install the Stripe CLI with `winget install Stripe.StripeCli`, then open a new terminal.

With `USE_MOCK_AI=true` the whole app runs with **zero AI network calls**: mocks return realistic output (including a fixture per sample email), so you can demo everything before adding keys.

### Demo tips
- **AI log page** (pulse icon, top right) lists every model call (model, latency, tokens, cost) and has **demo controls**. You can force rain, cold or heat to show the weather rules on any day, and in mock mode make the stylist return invalid item IDs to show validation and the rule-based fallback.
- **Add → From an order → "Try it with our sample order emails"** runs the 18 synthetic emails in `backend/samples/emails/` (Pro only).
- `python scripts/seed.py` resets to a fresh demo wardrobe at any time; the API can stay running.
- New model fields don't need a reset: on startup the API adds any missing columns to `stripefit.db`, with each field's default. Renames and type changes still need `seed.py`.
- The AI log and demo controls (`/api/debug/*`) have no login. Set `DEMO_CONTROLS=false` in `backend/.env` to switch them off if the app is ever deployed.

## What you (a human) need to do

Everything else (code, models, sample data, Stripe product setup scripts) is done. These steps need your accounts:

### 1. OpenRouter key (real AI)
1. Create a key at <https://openrouter.ai/keys> and add a few dollars of credit (the whole demo costs cents).
2. In `backend/.env` set `OPENROUTER_API_KEY=sk-or-...` and `USE_MOCK_AI=false`. The API reloads by itself.
3. Optional: run `python scripts/check_models.py` from `backend/`. It runs each configured model on real calls and reports which return valid JSON.
4. Optional: run `python scripts/check_outfits.py` from `backend/` to score the stylist on fixed scenarios (event rules, weather, taste).
5. Optional: run `python scripts/check_extraction.py` from `backend/`. It sends each sample order email to the real model and compares the result with the expected answer (refund matched, exchange old/new, child size, gift, German, unknown colour, injection ignored). Any `DIFF` line says what to tune in `app/ai/prompts.py`.

### 2. Stripe test keys (Pro purchase)
1. In the Stripe dashboard, switch to **Test mode**. Under **Developers → API keys**, copy the keys.
2. In `backend/.env` set `STRIPE_SECRET_KEY=sk_test_...` and `STRIPE_PUBLISHABLE_KEY=pk_test_...`.
3. From `backend/`, run:
   ```bash
   python scripts/stripe_setup.py      # creates "StripeFit Pro" + €2.99 price, writes STRIPE_PRICE_ID
   python scripts/stripe_listen.py     # writes STRIPE_WEBHOOK_SECRET, then forwards webhooks (leave running)
   ```
   `stripe_listen.py` passes your test key to the Stripe CLI, so **`stripe login` isn't needed**. It works on Windows, macOS and Linux (`./scripts/stripe_listen.sh` still works too). If the Stripe CLI is missing, install it with `winget install Stripe.StripeCli` on Windows or `brew install stripe/stripe-cli/stripe` on macOS.
4. In the app, go to **Pro → Buy**, pay with card `4242 4242 4242 4242`, any future expiry and any CVC.
5. To check that a replayed webhook doesn't create a second purchase: `stripe events resend <evt_id> --api-key sk_test_...`

Step 3 is optional: checkout also works without `STRIPE_PRICE_ID` (inline price) or the webhook, because the success page confirms the payment with Stripe directly.

### 3. Gmail import (optional, Pro)
1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API**.
2. Set up the **OAuth consent screen**: External, Testing. Add yourself and your teammates as **test users**.
3. Under **Credentials → Create credentials → OAuth client ID**, choose **Web application**. Use the authorised redirect URI `http://localhost:8000/api/gmail/callback`.
4. In `backend/.env` set `GOOGLE_CLIENT_ID=...` and `GOOGLE_CLIENT_SECRET=...`.
5. In the app, go to **Add → Gmail → Connect Gmail** and approve the consent screen (read-only).

### 3b. Google Calendar (optional): tomorrow's outfit planned around your day
Uses the same Google Cloud project and OAuth client as Gmail.
1. Enable the **Google Calendar API** in that project.
2. Add the scope `.../auth/calendar.events.readonly` to the OAuth consent screen.
3. Add the redirect URI `http://localhost:8000/api/calendar/callback` to the OAuth client.
4. Restart the API and open the link from `GET /api/calendar/auth-url`.

Until then, `POST /api/debug/demo-calendar` fakes tomorrow's events. See `HANDOFF.md` for the night-before notification.

### 4. Real clothes
Upload photos of your own clothes on **Add → Photos**. The seed data covers you until then.

## How it works

```
backend/app/
  ai/client.py          call_json(): OpenRouter only, timeout, 1 transport retry, 1 validation retry,
                        Pydantic validation, AICall logging, mock mode. Raises AIError, never returns junk.
  ai/prompts.py         every prompt says "do not guess"; email text is fenced as untrusted data
  ai/mocks/             fixtures + dynamic mocks (outfit picks must reference real candidate IDs)
  services/rules.py     ALL outfit business rules as constants (formality table, rain/cold/heat thresholds)
  services/outfit_engine.py   parse → weather → rules filter → AI pick → validate IDs → retry → rule-based fallback
  services/weather.py   Open-Meteo geocoding (+ aliases for campuses/docks it misses) + hourly forecast; any failure = "outfit ignores weather"
  services/redact.py    strips emails, phones, Eircodes, card numbers and address blocks before any model sees email text
  services/email_extract.py   read (.eml/.html/.txt/.pdf/screenshot) → pre-filter (no AI) → redact → extract
  services/ingest_jobs.py     uploads run as a background job; the page polls for progress (real AI can take a minute)
  services/reconcile.py order lifecycle, idempotent on retailer|order_id|item|size
  services/dedupe.py    definite (same order line) / likely (same or similar photo) / possible (same shop, similar name)
  services/stripe_service.py  Checkout + verified activation (signed webhook or retrieved session), idempotent
  services/gmail.py     gmail.readonly, PKCE, allowlisted senders + order subjects only, max 100, oldest first
frontend/src/           React + TypeScript + Tailwind, mobile-first, bottom nav: Wardrobe · Add · Review · Plan · Pro
```

### Trust and safety rules (enforced in code)
- **The app never breaks because AI failed.** Request parsing falls back to keyword rules, outfit picks to a deterministic per-slot pick, and photo labelling to "please fill in". Order extraction reports "AI unavailable" and retries next time.
- **AI output is never trusted blindly.** Outfit picks may only use IDs from the candidate list. Every AI item goes to the Review queue, and unknown values stay unknown.
- **Email is untrusted data.** It's redacted before the model sees it and fenced with `<<<EMAIL_DATA … EMAIL_DATA>>>`. Only extracted item fields are stored, and email bodies never are. Unknown sender domains are skipped without calling the AI. Product images are fetched over https only, from public hosts, with a 5 MB cap.
- **Stripe is test mode only.** Pro activates only from a signed webhook or a Checkout Session retrieved from Stripe with `payment_status == "paid"`.
- **Secrets** live only in `backend/.env` (gitignored). The Gmail token (`backend/.gmail_token.json`) is gitignored too.

### Model choices
Chosen from the OpenRouter catalogue (`python scripts/list_models.py`). Each task has a primary model plus two fallbacks from other providers:

| Task | Primary | Fallbacks | Why |
|---|---|---|---|
| Vision (labelling, screenshots) | `anthropic/claude-haiku-5.5` | `google/gemini-3.1-flash-lite`, `openai/gpt-4.1-mini` | Strong image understanding at $0.10/M input |
| Fast (parse request, extract emails) | `google/gemini-2.5-flash-lite` | `anthropic/claude-haiku-5.5`, `openai/gpt-4.1-nano` | Cheap, fast, reliable JSON |
| Stylist (outfit pick) | `anthropic/claude-sonnet-5.5` | `openai/gpt-4.1`, `google/gemini-2.5-flash` | Better taste and rule-following, at under €0.01 per outfit |

Change them in `backend/.env` (never hard-coded).

## API overview
`GET /api/health` · `GET /api/me` · `GET/POST/PATCH/DELETE /api/items` · `POST /api/items/{id}/status` · `POST /api/items/wash-worn` · `POST /api/items/laundry-done` · `POST /api/items/bulk-delete` · `POST /api/ingest/photo` · `POST /api/ingest/email|samples` (starts a background job) · `GET /api/ingest/jobs/{id}` (progress + summary) · `GET /api/review` · `POST /api/review/{id}/confirm|reject` · `POST /api/outfits/plan` · `GET /api/outfits` · `POST /api/outfits/{id}/swap|wear|feedback` · `POST /api/stripe/checkout` · `POST /api/stripe/webhook` · `GET /api/stripe/session/{id}` · `GET /api/gmail/status|auth-url|callback` · `POST /api/gmail/import|disconnect` · `GET /api/debug/ai-calls` · `GET /api/daily?day=today|tomorrow` · `POST /api/daily/another` · `GET /api/calendar/status|auth-url|callback|events` · `POST /api/calendar/disconnect` · `GET/PUT /api/daily/settings` · `GET /api/push/config` · `POST /api/push/subscribe|unsubscribe|test` · `GET /api/style/profile` · `PUT /api/style/preferences`

Interactive docs: <http://localhost:8000/docs>
