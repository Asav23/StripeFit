# StripeFit — build plan

Target users: students (uni days, nights out, sport, interviews, weddings, work).
Core promise: *"Tell StripeFit where you're going; it picks an outfit from clothes you own, that are clean, and that suit the weather."*

**Claude Code does everything except steps marked HUMAN.** Phases are in priority order; if time runs short, drop Phase 7 first. After each phase, verify by running the app and hitting the endpoints (no unit tests), then commit.

| Phase | What | Est. |
|---|---|---|
| 0 | Scaffold, config, health check | 20 min |
| 1 | Data model, wardrobe CRUD, seed data, wardrobe UI | 60 min |
| 2 | OpenRouter client, model selection, photo labelling, review queue | 60 min |
| 3 | Outfit engine (parse → weather → rules → AI pick → validate) | 75 min |
| 4 | Stripe one-time pass (StripeFit Pro) | 40 min |
| 5 | Status, laundry, edit/delete, duplicates | 30 min |
| 6 | Order email / screenshot extraction + reconciliation | 60 min |
| 7 | Gmail OAuth import | 45 min |
| 8 | UI polish and error handling pass | 20 min |

---

## HUMAN steps (the only things Claude Code can't do)

Claude Code should ask for each one when it reaches the phase that needs it, and keep working on other things meanwhile.

| When | HUMAN does | Paste into `backend/.env` |
|---|---|---|
| Phase 2 | Create an OpenRouter API key | `OPENROUTER_API_KEY` |
| Phase 4 | Copy Stripe **test** keys from the dashboard; run `stripe login` once in a terminal | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` |
| Phase 4 | Click through Stripe Checkout once with test card `4242 4242 4242 4242` | — |
| Phase 7 | Google Cloud: create project → enable Gmail API → OAuth consent screen (External, Testing) → add teammates as test users → create Web OAuth client with redirect URI `http://localhost:8000/api/gmail/callback` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Phase 7 | Click "Connect Gmail" and approve the consent screen | — |
| Any time | Upload real photos of your clothes through the app (seed data covers you until then) | — |

Everything else (model choice, Stripe product and price, webhook secret, sample emails, seed data) Claude Code does itself.

---

## Configuration (`backend/.env.example`)

```
OPENROUTER_API_KEY=
OPENROUTER_APP_NAME=StripeFit
MODEL_VISION=            # chosen by Claude Code in Phase 2
MODEL_VISION_FALLBACKS=
MODEL_FAST=
MODEL_FAST_FALLBACKS=
MODEL_STYLIST=
MODEL_STYLIST_FALLBACKS=
USE_MOCK_AI=false
AI_TIMEOUT_SECONDS=45

STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=   # filled by Claude Code from `stripe listen`
STRIPE_PRICE_ID=         # filled by Claude Code from stripe_setup.py
FRONTEND_URL=http://localhost:5173

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/gmail/callback

DEFAULT_LOCATION_NAME=Dublin
DEFAULT_LAT=53.3498
DEFAULT_LON=-6.2603
TIMEZONE=Europe/Dublin
FREE_ITEM_LIMIT=20
```

---

## Phase 0 — Scaffold (20 min)

1. Create `backend/` (FastAPI) and `frontend/` (Vite React TS + Tailwind + React Router) per the `CLAUDE.md` layout. Initialise git with remote `https://github.com/Asav23/StripeFit.git`.
2. `requirements.txt`: fastapi, uvicorn[standard], sqlmodel, pydantic, pydantic-settings, python-multipart, python-dotenv, openai, httpx, stripe, google-auth, google-auth-oauthlib, google-api-python-client, beautifulsoup4, pillow, imagehash, pypdf.
3. `config.py` loads `.env` via pydantic-settings. `.gitignore` covers `.env`, `.venv`, `node_modules`, `uploads/`, `*.db`, `.gmail_token.json`. Create `.env` from `.env.example` with `USE_MOCK_AI=true`.
4. `GET /api/health` → `{"ok": true, "mock_ai": bool}`. Vite proxy `/api` and `/uploads` → 8000.
5. Frontend shell: bottom nav **Wardrobe · Add · Review · Plan · Pro**.

**Verify:** both servers run; the frontend shows backend health.

---

## Phase 1 — Data model + wardrobe (60 min)

### Tables (SQLModel)

**Item**
- `id`, `name`, `image_path`, `thumb_path`
- `category`: `top | bottom | one_piece | outerwear | shoes | accessory | sportswear`
- `colours`: JSON list (or `["unknown"]`)
- `formality`: 1–5 or null (1 gym/lounge, 3 smart casual, 5 black tie); `warmth`: 1–5 or null; `waterproof`: bool | null; `material`: str | null
- `owner`: `me | child | other | unknown` (only `me` is used for outfits)
- `status`: `available | worn | in_wash | unavailable | on_the_way | returned`
- `confirmed`: bool (false = in review queue); `confidence`: float | null
- `source`: `photo | email | gmail | manual`; `source_ref`: `retailer|order_id|normalised_name|size` (indexed)
- `retailer`, `size`, `price`, `currency`, `last_worn`, `created_at`

**Outfit**: `id`, `request_text`, `parsed` (JSON), `weather` (JSON | null), `item_ids` (JSON), `explanation`, `gaps` (JSON), `used_fallback`, `feedback` (`up | down | null`), `created_at`

**User** (single row id=1): `premium`, `premium_since`

**Purchase**: `id`, `stripe_session_id` (unique), `amount_total`, `currency`, `status`, `created_at`

**AICall**: `id`, `task`, `model`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `cost`, `success`, `error`, `created_at`

**IngestLog**: `id`, `source`, `ref` (filename or Gmail message ID), `email_type`, `items_found`, `items_skipped`, `notes` (JSON skip reasons), `created_at`

### Endpoints
- `GET /api/me` → `{premium, confirmed_item_count, item_limit}`
- `GET /api/items?status=&category=&confirmed=true` · `POST /api/items` · `PATCH /api/items/{id}` · `DELETE /api/items/{id}`
- Serve `/uploads/...` via StaticFiles.

### Seed
`scripts/seed.py`: ~15 confirmed items across every category and formality level, including a waterproof jacket, suede shoes, trainers, a blazer and suit trousers, a dress, sportswear. Generate simple placeholder images (Pillow: coloured tile with the item name).

### Frontend — Wardrobe page
Grid of item cards (image, name, category, colour dots, status chip), filters by category/status, detail drawer with edit and delete.

**Verify:** seeded items show; edit and delete work.

---

## Phase 2 — AI client, model selection, photo labelling, review queue (60 min)

**HUMAN:** OpenRouter API key → `.env`. Until then keep `USE_MOCK_AI=true` and build against mocks.

### `app/ai/client.py`
- `OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`, headers `HTTP-Referer: http://localhost`, `X-Title: StripeFit`.
- `call_json(task, model, fallbacks, messages, schema) -> BaseModel`:
  - `extra_body={"models": [model, *fallbacks]}` for OpenRouter fallback routing;
  - ask for JSON only (`response_format={"type":"json_object"}` where supported; otherwise extract the first JSON object from the text);
  - validate with Pydantic; on failure retry **once** with the validation errors appended;
  - one short backoff retry on 429 / 5xx / timeout;
  - log every call to `AICall` (read `usage` from the response);
  - raise a typed `AIError` that routers turn into friendly messages.
- Images: resize to max 1024 px, send as `data:image/jpeg;base64,...` in an `image_url` content part.
- Mock mode returns fixtures from `app/ai/mocks/{task}.json` (write realistic ones).

### Model selection (Claude Code does this)
`scripts/list_models.py` fetches `https://openrouter.ai/api/v1/models`. Pick:
- `MODEL_VISION`: a capable model that accepts image input, at low cost per image;
- `MODEL_FAST`: cheap, fast, reliable at JSON;
- `MODEL_STYLIST`: a stronger general model;
- two fallbacks each (different providers).

Run each candidate on 2–3 real calls to confirm valid JSON, write choices to `.env`, and tell the human what was chosen and why in two lines.

### Labelling
- Schema `ClothingLabels`: `name`, `category`, `colours`, `formality`, `warmth`, `waterproof`, `material`, `is_clothing`, `confidence` (0–1), `notes`.
- Prompt rules: describe only what's visible; `"unknown"`/null when unsure, never guess; if several items or a person wearing an outfit, label the most prominent item and say so in `notes`; non-clothing → `is_clothing=false`.
- `POST /api/ingest/photo` (multipart, multiple files; JPEG/PNG/WebP, max 10 MB each; friendly error otherwise): save original + thumbnail → label → `Item(confirmed=False, source="photo")`. Non-clothing → no item, return message.
- Free limit: confirmed items ≥ `FREE_ITEM_LIMIT` and not premium → HTTP 402 `{code:"upgrade_required"}`.

### Review queue
- `GET /api/review` · `POST /api/review/{id}/confirm` (edited fields) · `POST /api/review/{id}/reject`.
- **Review page:** image plus AI labels as editable chips/selects; low-confidence fields highlighted; unknown fields flagged "please fill in"; Confirm / Reject.

### Frontend — Add page, "Photos" tab
Camera/gallery upload (`<input type="file" accept="image/*" capture="environment" multiple>`), progress per photo, then link to Review.

**Verify:** a photo becomes a labelled pending item → confirm → appears in Wardrobe. A non-clothing image is rejected gracefully.

---

## Phase 3 — Outfit engine (75 min) — the heart of the app

`POST /api/outfits/plan {request_text}` → Outfit. In `services/outfit_engine.py`:

### 1. Parse request (MODEL_FAST)
Schema `ParsedRequest`: `occasion` (`uni | casual | night_out | date | interview | work | wedding | funeral | sport | other`), `occasion_detail`, `destination` (str | null), `datetime_iso` (resolve "tomorrow at 10" from the current Europe/Dublin time given in the prompt; default: next sensible time today), `travel_mode` (`walk | cycle | bus | train | car | unknown`), `dress_code` (str | null), `needs_clarification` (str | null — only for empty or meaningless requests).
If `needs_clarification` is set, return it as a question for the UI instead of an outfit.

### 2. Weather (`services/weather.py`)
- Geocode via `https://geocoding-api.open-meteo.com/v1/search?name=...&count=1`; if not found, use Dublin and say so.
- Forecast via `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code&timezone=Europe/Dublin`; take the hour nearest `datetime_iso`.
- Past time, beyond forecast range or API failure → `weather=None` plus UI notice "No forecast available; outfit ignores weather."

### 3. Rules filter (constants in one file)
```
OCCASION_FORMALITY = {  # (min, max)
  "sport": (1, 1), "casual": (1, 3), "uni": (1, 3), "night_out": (2, 4), "date": (2, 4),
  "work": (3, 4), "interview": (4, 5), "wedding": (4, 5), "funeral": (4, 5), "other": (1, 5)}
```
- Candidates: confirmed, `owner == "me"`, `status == "available"`.
- Formality within range (null formality allowed only for casual/uni/other). Sport prefers `sportswear`.
- Wet = rain probability ≥ 50% or precipitation ≥ 0.5 mm. If wet and travel is walk/cycle/bus/train/unknown: outerwear must be waterproof if any exists (else gap "no waterproof coat"); exclude suede/canvas shoes.
- Below 10 °C: outerwear warmth ≥ 3; below 5 °C: ≥ 4. Above 20 °C: exclude outerwear/tops with warmth ≥ 4.
- Group into slots `top`, `bottom`, `one_piece`, `outerwear`, `shoes`, `accessory`.
- Empty required slot → `gaps` entry with a helpful suggestion (borrow, second-hand).

### 4. AI pick (MODEL_STYLIST)
Send only candidates (id, name, category, colours, formality, warmth, waterproof, material, days since last worn) + parsed request + weather summary.
Schema `OutfitPick`: `top_id`, `bottom_id`, `one_piece_id`, `outerwear_id`, `shoes_id`, `accessory_ids`, `explanation` (≤ 60 words, mentions occasion and weather), `confidence`.
Rules in prompt: only the given IDs; either one_piece or top + bottom; colours that work together; prefer items not worn recently; outerwear only if weather or occasion needs it.

### 5. Validate + fallback
Check every ID is a candidate in the right slot and the structure is valid. Retry once with the errors; if still invalid, rule-based pick per slot (formality closest to the occasion midpoint, then least recently worn), `used_fallback=true`, template explanation. Save the Outfit.

### Other endpoints
- `POST /api/outfits/{id}/swap {slot}` → re-pick that slot excluding the current item.
- `POST /api/outfits/{id}/wear` → items `status=worn`, `last_worn=now`.
- `POST /api/outfits/{id}/feedback {up|down}` · `GET /api/outfits` (history).

### Frontend — Plan page
Text box plus example chips ("Interview tomorrow 10am in Grand Canal Dock, walking", "Football training tonight", "Night out Saturday in town"). Result card: item images per slot, weather chip (temp, rain %, icon), explanation, gaps in an amber box, "fallback used" badge, buttons **Wear this** / **Swap [slot]** / 👍 👎. Clarification questions shown as a prompt to refine.

**Verify (run these requests yourself):** rainy walking interview → waterproof coat, no suede shoes; football training → sportswear; delete all shoes → gap, no crash; forced invalid mock output → fallback used.

---

## Phase 4 — Stripe: StripeFit Pro (40 min)

**HUMAN:** Stripe test keys → `.env`; run `stripe login` once.

**Offer:** one-time **€2.99 StripeFit Pro** — unlimited items (free: 20) plus order-email and Gmail import. Show the rationale on the page: students dislike subscriptions; a one-off price under the cost of a coffee fits a student budget.

Claude Code:
1. Write and run `scripts/stripe_setup.py`: create Product "StripeFit Pro" + Price `unit_amount=299, currency="eur"` (one-time); write `STRIPE_PRICE_ID` to `.env`.
2. Run `stripe listen --forward-to localhost:8000/api/stripe/webhook` in the background; write the `whsec_...` to `STRIPE_WEBHOOK_SECRET`.
3. `POST /api/stripe/checkout` → `stripe.checkout.Session.create(mode="payment", line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}], success_url=f"{FRONTEND_URL}/pro/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{FRONTEND_URL}/pro", client_reference_id="1", metadata={"product": "stripefit_pro"})` → `{url}`.
4. `POST /api/stripe/webhook`: raw body + `stripe.Webhook.construct_event(...)`; bad signature → 400; on `checkout.session.completed` with `payment_status == "paid"` → `activate_pro(session)`.
5. `GET /api/stripe/session/{id}`: retrieve the session; if paid → same `activate_pro` (covers webhook delay).
6. `activate_pro` is idempotent: upsert `Purchase` by session ID, set `User.premium=true`.
7. Gating: email/Gmail import and > `FREE_ITEM_LIMIT` items → 402 `upgrade_required`; frontend shows an upgrade banner linking to Pro.

**Frontend — Pro page:** €2.99 EUR one-time, what you get, why one-time; "Buy StripeFit Pro" → Checkout. Success page polls `/api/stripe/session/{id}` then `/api/me`, shows "Pro active" and the purchase record (amount, currency, date, session ID). Pro badge in header.

**HUMAN:** complete one test checkout with card `4242 4242 4242 4242`.

**Verify:** after checkout, premium is active, gated features unlock, and a replayed webhook (`stripe events resend <id>`) doesn't duplicate the purchase.

---

## Phase 5 — Status, laundry, duplicates (30 min)

- `POST /api/items/{id}/status {status}`; `POST /api/items/laundry-done` (all `in_wash` → `available`); "Put worn items in wash" button (`worn` → `in_wash`).
- **Duplicates** (`services/dedupe.py`) when confirming a review item:
  1. exact `source_ref` match → definite;
  2. same category + overlapping colour + perceptual image hash distance ≤ threshold → likely;
  3. same category + retailer + similar name → possible.
- Review UI: "Looks like your navy blazer — same item?" → **Merge** (keep better image/labels) / **Keep both**. Quantity 2 from one order = two items, not duplicates.
- Wardrobe: multi-select delete; "unavailable" toggle (lent out, at home, etc.).

**Verify:** the same photo uploaded twice prompts a merge; laundry changes what the Plan page can pick.

---

## Phase 6 — Order email / screenshot extraction (60 min, Pro)

### Sample data (Claude Code generates)
Write ~12 realistic **synthetic** order emails as `.eml` in `backend/samples/emails/` (fictional names, addresses and order numbers) covering: clean order; order + dispatch + delivery of the same order; split shipment; refund; exchange of sizes; two identical T-shirts; child-size item; gift order; basket reminder; price-drop marketing; German-language order; vague item name with no colour; non-clothing item from a clothing retailer; fake order from an unknown domain containing "ignore previous instructions". Use them to check the feature works.

### `POST /api/ingest/email` (multipart; `.eml`, `.html`, `.txt`, `.pdf`, `.png/.jpg`)
1. **Read:** `.eml` via Python `email` (text/plain preferred, else HTML → text via BeautifulSoup keeping `<img>` alt text and product image URLs); `.pdf` via pypdf; images → vision model.
2. **Pre-filter (no AI):** skip basket/cart reminders, price drops, wishlists, newsletters, review requests, and unknown sender domains for `.eml`; record reasons in `IngestLog`.
3. **Redact (`services/redact.py`):** email addresses, phone numbers, Eircodes (`[A-Z]\d[\dW]\s?[A-Z\d]{4}`), card numbers / "ending in", and lines under "Delivery address", "Billing address", "Shipping to" and similar.
4. **Extract (MODEL_FAST; MODEL_VISION for screenshots):** text wrapped in `<<<EMAIL_DATA ... EMAIL_DATA>>>`, marked as data not instructions. Schema `OrderExtraction`:
   - `email_type`: `order_confirmation | dispatch | delivery | refund | return | cancellation | exchange | marketing | other`
   - `retailer`, `order_id`, `currency`, `order_date`
   - `items`: `{name, category, colours, size, quantity, price, is_clothing, likely_for: me|child|gift|unknown, image_url, status_hint: kept|cancelled|out_of_stock|unknown}`
   - `confidence`
   - Never invent colours or sizes. Child sizes ("age 7–8", "3–4Y", kids' EU sizes) → `child`; gift wrap/message/different recipient → `gift`.
5. **Reconcile (`services/reconcile.py`)**, key `retailer|order_id|normalised_name|size`:
   - confirmation → one pending item per unit of quantity (skip non-clothing, cancelled, out of stock), status `on_the_way`;
   - dispatch/delivery → match, no new items; delivery → `available`;
   - refund/return/cancellation → matching items `returned` (pending ones removed);
   - exchange → old size returned, new size added;
   - marketing/other → ignore and log;
   - `likely_for != me` → pending with owner preset and an "Is this yours?" prompt.
6. Download `image_url` server-side (timeout, 5 MB cap); otherwise placeholder plus "add a photo" prompt.

**Frontend — Add page, "From an order" tab:** drag-and-drop multiple files; summary ("4 items found · 2 skipped: not clothing · 1 ignored: basket reminder"); items go to Review with source badges.

**Verify:** upload all sample emails — no duplicates from confirmation + dispatch, refund removes the item, child item asks "Is this yours?", marketing and the fake email create nothing, German email extracts.

---

## Phase 7 — Gmail OAuth import (45 min, Pro, drop first if short on time)

**HUMAN:** Google Cloud setup (see table) → client ID/secret in `.env`; later approve the consent screen.

- `GET /api/gmail/auth-url` (`google_auth_oauthlib.flow.Flow`, scope `https://www.googleapis.com/auth/gmail.readonly`, `access_type=offline`, `prompt=consent`) · `GET /api/gmail/callback` → save token to `.gmail_token.json`, redirect to `/add?gmail=connected` · `GET /api/gmail/status` · `POST /api/gmail/disconnect` (delete token).
- `POST /api/gmail/import {months: 12}`: query `newer_than:{months}m subject:(order OR confirmation OR receipt OR shipped OR dispatched OR delivered OR refund OR return) from:(<allowlist>)`. Allowlist constant: zalando, asos, zara, hm, uniqlo, nike, adidas, jdsports, boohoo, shein, vinted, depop, ebay, arnotts, brownthomas, primark, very, next, schuh, riverisland, mango, cos, arket, urbanoutfitters, pullandbear, bershka, stradivarius, massimodutti, lululemon, gymshark, thenorthface, patagonia.
- Max 100 messages; process oldest → newest so refunds reconcile after orders; reuse Phase 6 from step 2; skip message IDs already in `IngestLog`.
- UI: "Connect Gmail" with a plain explanation of what's read (read-only, order emails from listed shops, last 12 months, email bodies never stored), progress, same results summary.

**Verify:** after the human connects, import creates pending items; re-running adds nothing new; disconnect works.

---

## Phase 8 — Polish pass (20 min)

- Loading skeletons for every AI action; toasts for errors with a next step; empty states ("Add your first item").
- Friendly handling for: empty or very long requests, unsupported/oversized files, empty wardrobe, everything in the wash, no network to OpenRouter or Open-Meteo.
- Small "AI log" page (`GET /api/debug/ai-calls`): model, latency, tokens, cost per call.
- Run the whole flow once from a fresh database and fix anything broken. Final commit and push.

---

## First prompt to give Claude Code

> Read `CLAUDE.md` and `PLAN.md`, then build StripeFit phase by phase. Do everything yourself except the steps marked HUMAN; when you reach one, tell me exactly what to do and where to paste it, and keep working on other parts meanwhile. Use `USE_MOCK_AI=true` until I give you the OpenRouter key. No unit tests — verify by running the app. Commit and push after each phase, and give me a two-line update.
