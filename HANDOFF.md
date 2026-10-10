# StripeFit backend: handoff

**Branch:** `backend-complete-1` · **Date:** 10 October 2026

Read `CLAUDE.md` (project rules) and `PLAN.md` (phased spec) first. This file says where the backend stands and what's left.

## Status in one paragraph

All 8 phases in `PLAN.md` are built. Every backend gap that could be closed without API keys is closed. The whole app passes a 68-check end-to-end smoke test in **mock AI mode**. **Nothing has run against real OpenRouter, Stripe or Google yet**, because no keys were available. The remaining work is: add the keys, verify each integration for real, and fix whatever that turns up.

## What's left to do

### 1. Real AI (needs an OpenRouter key)
1. In `backend/.env`, set `OPENROUTER_API_KEY=sk-or-...` and `USE_MOCK_AI=false`.
2. Run `python scripts/check_models.py` from `backend/`. Replace any model that fails or no longer exists on OpenRouter (`python scripts/list_models.py <filter>`). Keep two fallbacks from different providers. Model names go in `.env` only.
3. Run `python scripts/check_extraction.py`. It sends each sample order email to the real model and compares the result with the expected answer. Each `DIFF` line names the field that's wrong. Tune `EXTRACT_SYSTEM` in `app/ai/prompts.py` until all 15 match. The other 3 samples are skipped before any AI call, which is correct.
4. On the Plan page, try the three example requests. Check that `used_fallback` is false, the explanation is 60 words or fewer, and it mentions the occasion and the weather.
5. Upload a few real clothing photos and one non-clothing photo. Tune `LABEL_SYSTEM` in `app/ai/prompts.py` if the labels are poor.
6. Open the AI log page (pulse icon). Tokens and cost should be filled in. Cost parsing was checked against a simulated OpenRouter response, but not a live one.

### 2. Stripe Pro purchase (needs Stripe test keys)
1. In the Stripe dashboard, switch to **Test mode**. In `backend/.env`, set `STRIPE_SECRET_KEY=sk_test_...` and `STRIPE_PUBLISHABLE_KEY=pk_test_...`.
2. Run `python scripts/stripe_setup.py`. It creates the product and the €2.99 price, and writes `STRIPE_PRICE_ID` into `.env`.
3. Run `python scripts/stripe_listen.py` and leave it running. It writes `STRIPE_WEBHOOK_SECRET` into `.env` and forwards webhooks to the API. It needs the Stripe CLI: `winget install Stripe.StripeCli` on Windows, `brew install stripe/stripe-cli/stripe` on Mac.
4. In the app, go to **Pro → Buy** and pay with card `4242 4242 4242 4242`, any future expiry and any CVC.
5. Check that the success page shows the receipt, `/api/me` returns `premium: true`, and there is exactly one Purchase.
6. Resend the event with `stripe events resend <evt_id> --api-key sk_test_...`. It must not create a second Purchase.

Pro unlocks order-email and Gmail import. **Those screens, including the new import progress bar, can't be tested in the UI until this step is done.** To go back to the free plan, use the reset button on the Pro page or re-run `scripts/seed.py`.

### 3. Gmail import (needs a Google OAuth client; lowest priority)
1. In Google Cloud Console, create a project and enable the **Gmail API**.
2. Set up the OAuth consent screen as External, in Testing mode, and add each teammate as a test user.
3. Create an OAuth client ID of type **Web application**, with the redirect URI `http://localhost:8000/api/gmail/callback`.
4. In `backend/.env`, set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
5. In the app, go to **Add → Gmail → Connect Gmail** and approve the consent screen. Then import, and check that re-running imports nothing new and that Disconnect works.

### 4. Click through the UI
Nobody has clicked through the frontend redesign (commit `90b5ed5`) yet. It type-checks and builds, and every page loads. Check that:
- every error shows a friendly message with a next step;
- every AI action shows a loading state;
- the layout works at phone width.

## Done on this branch

| Change | Where |
|---|---|
| Email uploads run as a background job; the Add page polls for progress. Email and Gmail imports can't overlap. | `services/ingest_jobs.py`, `routers/ingest.py`, `frontend/src/components/OrderImporter.tsx` |
| Weather finds Dublin places Open-Meteo misses (UCD, Grand Canal Dock, Trinity, DCU, venues), plus accent and ", Dublin" variants | `services/weather.py` (`PLACE_ALIASES`) |
| Keyword parser stops place names at day words ("Temple Bar Saturday" → "Temple Bar") | `services/request_rules.py` |
| Gmail sign-in survives an API reload: the PKCE verifier is kept in a gitignored file with a 15-minute expiry | `services/gmail.py` |
| Missing database columns are added on startup, with model defaults and indexes | `db.py` (`add_missing_columns`) |
| HEIC photos accepted when `pillow-heif` loads | `services/images.py` |
| `DEMO_CONTROLS=false` switches off the unauthenticated `/api/debug/*` | `routers/debug.py`, `config.py` |
| Cross-platform Stripe webhook script; the `.sh` now calls it | `scripts/stripe_listen.py` |
| Real-model extraction check against the expected answers | `scripts/check_extraction.py` |
| Windows fixes: `tzdata` for Europe/Dublin; frontend proxy to `127.0.0.1:8000` | `requirements.txt`, `frontend/vite.config.ts` |
| README: Windows setup section, new scripts and endpoint | `README.md` |

API change: `POST /api/ingest/email` and `POST /api/ingest/samples` now return `202` with a job. Poll `GET /api/ingest/jobs/{id}` for progress and the summary. The frontend is already updated.

## Verified (mock AI mode)
- **Smoke test, 68 of 68 checks passed.** It covers wardrobe CRUD and laundry, photos and the Review queue (duplicates, merge, non-clothing, AI down, HEIC), the free limit, and outfits for 4 occasions. It also covers rain rules, invalid AI picks, AI down and swap/wear. Stripe was tested with locally signed webhooks: bad signature, unpaid and triple delivery. It also covers all 18 sample emails, re-import, the injection email, Gmail without keys, and the debug pages. It ran on an in-memory database copy and isn't committed, because `CLAUDE.md` says no test suite.
- **Frontend:** `npx tsc --noEmit` passes, `npm run build` succeeds, and every route loads.

## Gotchas
- **Windows Application Control** can block SQLAlchemy's compiled extension ("DLL load failed … Application Control policy"). The fix is in the README Windows section.
- **Port 8000 on Windows** may also be used by Docker Desktop and WSL over IPv6. That's why the proxy uses `127.0.0.1`. Call the API at `http://127.0.0.1:8000`, not `localhost`.
- **Auto-reload on Windows** sends Ctrl+C to the server, so it needs a real terminal window. If the backend runs without a console, for example from a background job, reloads hang. Restart it by hand.
- **Mock mode** returns stock photo labels and generic outfit explanations. They won't match real photos, and that's expected.
- **The demo wardrobe** has 19 of 20 free items. Run `python scripts/seed.py` to reset everything, including Pro.
- **Phone testing:** run `npm run dev -- --host`. Stripe checkout and Gmail redirect back to `localhost`, so finish those on the computer.
- **Secrets** go in `backend/.env` only. Never commit `.env`, `.gmail_token.json` or `.gmail_oauth_pending.json`; all three are gitignored.

## Still open, by choice
- **Screenshots aren't redacted** before the vision model sees them. The UI asks users to crop out their address.
- **Demo switches reset on restart.** The weather override, mock overrides and import jobs are kept in memory.
- **The migration only adds columns.** Renaming a column or changing its type still needs `seed.py`.
