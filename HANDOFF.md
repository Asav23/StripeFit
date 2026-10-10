# StripeFit backend: handoff

**Branch:** `backend-complete-1` · **Date:** 10 October 2026

Read `CLAUDE.md` (project rules) and `PLAN.md` (phased spec) first. This file says where the backend stands and what's left.

## Status in one paragraph

All 8 phases in `PLAN.md` are built, plus event-aware and personalised outfit picks and a daily casual fit with morning notifications (backend only; see the sections below). Every backend gap that could be closed without API keys is closed. The whole app passes a 68-check end-to-end smoke test in **mock AI mode**. **Nothing has run against real OpenRouter, Stripe or Google yet**, because no keys were available. The remaining work is: add the keys, verify each integration for real, and fix whatever that turns up.

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

## Outfits that suit the event and the person (backend built)

**Goal:** the stylist model on OpenRouter picks the best combination for the event and learns what each user likes. Stages 1 to 4 below are built in the backend and tested in mock mode. Stage 5 is partly built. Real-model quality still has to be checked once the OpenRouter key is in: run `python scripts/check_outfits.py` and `python scripts/check_extraction.py`.

### What is built
- **Event knowledge.** `services/rules.py` holds `EVENT_STYLE_GUIDE`: what each occasion expects, what to avoid, good combinations, plus `COLOUR_RULES`. The guide for the occasion is sent with every pick, and the prompt (`PICK_SYSTEM`) sets the priority: hard rules, then the style guide, then the user's taste. Some rules are enforced in code, not just suggested:
  - no white, cream or ivory dress at a wedding (`AVOID_MAIN_COLOURS`);
  - bright colours are ranked lower at funerals and interviews (`DISPREFER_COLOURS`).
- **New occasions:** `debs`, `society`, `match` (watching), `festival`, `travel` and `presentation`, each with a formality range. Both the AI parser and the keyword parser know them. Unknown occasion words from the model map to `other` instead of failing.
- **Richer context.** `ParsedRequest` now has `setting` (indoor, outdoor or mixed), `duration_hours` and `activity`.
- **Weather for the whole event.** It's checked across the event's hours, using `DEFAULT_DURATION_HOURS` per occasion or the parsed duration. `WeatherOut` adds `window_hours`, `temperature_min_c`, `temperature_max_c` and `precipitation_probability_max`. Coats and layers are chosen for the coldest hour, and rain for the wettest.
- **Taste learning, with no training run.** The `StyleSignal` table records thumbs up or down (toggling replaces, it doesn't stack), swaps (the item rejected and the item chosen) and worn outfits. `services/style_profile.py` builds a profile from these signals plus stated preferences:
  - liked and avoided colours;
  - loved and rejected items;
  - dressier or more relaxed than usual, per occasion;
  - past liked outfits.

  The model gets a compact `user_taste` summary. The rule-based ranking, used for the fallback and mock mode, scores items by the same signals. Signals decay over 60 days. The profile only reorders candidates that already passed the rules.
- **Measuring.** `python scripts/check_outfits.py [--mock]` runs 14 fixed scenarios against a fixed test wardrobe, with 28 code checks. It covers formality, rain, cold, heat, no white at a wedding, no bright colours at a funeral, sportswear for sport, and loved or avoided items. It scores 28 of 28 with the rule-based picker. Run it before and after every prompt change.
- **Training data.** `python scripts/export_style_dataset.py` writes one JSON line per outfit: context, weather, item features, thumbs, worn and swaps. It goes to `backend/exports/`, which is gitignored. Free text is left out unless you pass `--include-text`.

### Still to do
1. **Real-model check.** With the OpenRouter key in, run `check_outfits.py`. Tune `PICK_SYSTEM` or the style guide until the score holds, and check the explanations cite a style guide point or a taste reason.
2. **Frontend: style preferences screen.** Use `PUT /api/style/preferences` with `{favourite_colours, avoid_colours, style_notes}`, and `GET /api/style/profile?occasion=casual` to show what was learned.
3. **Frontend: labels for the new occasions** in `OCCASION_LABELS` in `frontend/src/lib/format.ts`. Until then the UI shows the raw key, such as `night_out`.
4. **Frontend: whole-event weather on the outfit card.** For example "down to 6° later", and the rain chance from `precipitation_probability_max`.
5. **Recording review edits as signals.** Not done yet, because they're about labels more than taste.
6. **Stage 5: actual training.** As far as we know, OpenRouter doesn't offer fine-tuning, so fine-tuning would break the "OpenRouter only" rule in `CLAUDE.md`, and that's a team decision. Today's per-user "re-ranker" is the signal-weighted scoring in `style_profile.preference_score()`. It is transparent, local, free and per user. A learned model, such as logistic regression on the exported dataset, could replace it later without touching the API.
7. **Multiple users.** Everything is keyed by `user_id` (always 1 today), so real accounts can be added without a rewrite.

## Daily casual fit + morning notification (backend built)

Every day there is a ready-made casual outfit, and optionally a browser notification each morning at a time the user picks.

**How it works.** `services/daily.py` builds today's request in code: casual, from 9am, 10 hours, walking, at the user's location or Dublin. It runs the normal pipeline: whole-day weather, rules, the user's taste, the AI stylist, then validation and the fallback. That costs one AI call a day.
- **"Another option"** avoids the pieces already suggested today.
- **Variety.** Yesterday's main pieces are avoided too, so the week doesn't repeat.
- **Saved as outfits.** Daily outfits are `Outfit` rows with `kind="daily"` and `for_date`. Swap, wear and feedback use the normal `/api/outfits/{id}/…` endpoints, so they teach the taste profile too.

**Notifications.** These are real browser push notifications (Web Push with VAPID), so no third-party account is needed.
- The VAPID keys are already generated in this machine's `backend/.env`. On a new machine, run `python scripts/make_vapid_keys.py` once. It refuses to overwrite existing keys, because that would break every subscribed browser.
- `services/scheduler.py` checks once a minute. It sends at most one notification a day, and it records the date it sent, so restarts never send twice.
- If the computer was asleep at notification time, it still sends within 3 hours. If the user switches notifications on after that window, they start tomorrow.
- Expired browser subscriptions are removed automatically.
- Turn the scheduler off with `DAILY_SCHEDULER_ENABLED=false`.
- Set `VAPID_SUBJECT` to a real team contact address before any deployment.

**API**

| Method and path | What it does |
|---|---|
| `GET /api/daily` | Today's fit, created on the first request of the day, plus the settings |
| `POST /api/daily/another` | A different fit for today |
| `GET /api/daily/settings` | `{enabled, time, location, push_configured, subscriptions, last_sent_date}` |
| `PUT /api/daily/settings` | Body `{enabled, time: "HH:MM", location}`, in Dublin time |
| `GET /api/push/config` | `{configured, public_key}`, the public key the browser needs to subscribe |
| `POST /api/push/subscribe` | Body is the browser's `PushSubscription.toJSON()` |
| `POST /api/push/unsubscribe` | Body `{endpoint}` |
| `POST /api/push/test` | Sends today's fit to every subscribed browser now |

**Verified in mock mode:**
- today's fit is created once and repeats on the second visit;
- "another option" changes the main pieces;
- an invalid time is rejected;
- the scheduler is not due before the set time, sends once at that time, and not again that day;
- there is no catch-up after 3 hours, and it's due again the next day;
- a real VAPID-signed, encrypted push was accepted by a test endpoint;
- an expired subscription (410) is removed.

**The frontend still needs to be built.** The backend is complete and the current UI doesn't use it yet. It needs:
1. **A service worker** at `/sw.js`, placed in `frontend/public/`. On `push`, it shows `{title, body}` from the JSON payload. On `notificationclick`, it opens `data.url`, which is `/plan?daily=1`.
2. **Subscribing.** Request `Notification` permission, call `pushManager.subscribe({userVisibleOnly: true, applicationServerKey: <public_key from /api/push/config, base64url-decoded>})`, then POST the result to `/api/push/subscribe` and `PUT /api/daily/settings` with `enabled: true`.
3. **A "Today's casual fit" card**, on the Plan page or home. Show `GET /api/daily` with the existing `OutfitCard`, plus an "Another option" button, a notification switch, a time picker and "Send a test".
4. **Unsubscribing.** Call `subscription.unsubscribe()`, then POST `/api/push/unsubscribe` and `PUT` settings with `enabled: false`.
5. **Browser support.** Push works in Chrome, Edge and Firefox on `localhost`. On iPhone, it only works once the site is added to the Home Screen, which needs https in production.

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
| Event style guide, 6 new occasions, colour rules, no white dress at weddings, whole-event weather | `services/rules.py`, `services/weather.py`, `app/ai/prompts.py` |
| Richer requests (setting, duration, activity) from the AI and keyword parsers | `schemas.py`, `services/request_rules.py` |
| Taste learning from thumbs, swaps and worn outfits; stated preferences | `services/style_profile.py`, `routers/style.py`, `StyleSignal` table |
| Daily casual fit, scheduler and Web Push notifications | `services/daily.py`, `services/scheduler.py`, `services/push.py`, `routers/daily.py`, `routers/push.py` |
| Outfit scenario checker, dataset export, VAPID key script | `scripts/check_outfits.py`, `scripts/export_style_dataset.py`, `scripts/make_vapid_keys.py` |

API change: `POST /api/ingest/email` and `POST /api/ingest/samples` now return `202` with a job. Poll `GET /api/ingest/jobs/{id}` for progress and the summary. The frontend is already updated.

## Verified (mock AI mode)
- **New features: 37 of 37 checks passed.** They cover the new occasions, the wedding colour rule, the style guide in the prompt, taste learning, the daily fit, the scheduler and push. `check_outfits.py --mock` scores 28 of 28. The original 68-check smoke test still passes.
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
