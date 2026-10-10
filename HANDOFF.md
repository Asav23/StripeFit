# StripeFit: handoff

**Branch:** `backend-complete-1` · **Date:** 10 October 2026

Read `CLAUDE.md` (project rules) and `PLAN.md` (phased spec) first. This file says where the app stands and what's left.

## Status in one paragraph

All 8 phases in `PLAN.md` are built, plus event-aware and personalised outfit picks, and a daily outfit planned from Google Calendar, the weather and your laundry, sent as a notification the night before. All of it has a frontend. **Stripe is now configured and verified in test mode.** Checkout pages are created, and a real signed webhook from Stripe was verified and handled. **AI still runs in mock mode**, because the key provided isn't an OpenRouter key. Google (Gmail and Calendar) is not configured yet. Test status: smoke test 67 of 68 (the one failure only expects Stripe to have no keys), new features 37 of 37, calendar, night-before and laundry 46 of 46, outfit scenarios 28 of 28, email extraction 15 of 15. The frontend type-checks and builds.

## What needs fixing (priority order)

| # | Problem | Why it matters | How to fix | Who |
|---|---|---|---|---|
| 1 | **The AI key is not an OpenRouter key.** `OPENROUTER_API_KEY` in `backend/.env` is 35 characters starting with `sk-`, which is DeepSeek's format. OpenRouter rejects it with 401. `USE_MOCK_AI` was set back to `true` so the app stays usable | No real photo labels, outfit picks or email extraction. Everything runs on mocks and rules | Create a key at https://openrouter.ai/keys (it starts `sk-or-v1-`) and add credit. Put it in `.env`, set `USE_MOCK_AI=false`, and restart the API. Then run `python scripts/check_models.py`, `check_outfits.py` and `check_extraction.py` from `backend/` and tune the prompts until they pass. The chosen models (`deepseek/deepseek-v4.1-flash`, `~deepseek/deepseek-pro-latest`, `openrouter/free`) all exist on OpenRouter. The vision model `openrouter/free` has no fallback, so add one, for example `deepseek/deepseek-v4-flash-vision-exp` or a Claude or Gemini model | Human: key. Dev: checks and tuning |
| 2 | **The DeepSeek key was pasted into a chat** | It's exposed | Rotate it in the DeepSeek dashboard if it's real | Human |
| 3 | **A Pro purchase hasn't been completed in the browser yet** | It's the payment flow judges will try | Make sure the webhook listener is running (`python scripts/stripe_listen.py`, which keeps `STRIPE_WEBHOOK_SECRET` in sync), go to **Pro → Buy**, pay with card `4242 4242 4242 4242`, and check that Pro switches on. Optionally resend the event and confirm no second Purchase appears | Human, 2 minutes |
| 4 | **Google isn't configured,** so Gmail import and the Google Calendar sign-in don't work. **No setup is needed for the calendar itself:** paste the private iCal link on the Today tab ("Your calendar" card). It's built and tested, and Outlook and iCloud links work too | The day planner falls back to casual days. Use the demo calendar on the AI log page meanwhile | Follow sections 3 and 3b below: Google Cloud project, Gmail API and Calendar API enabled, OAuth consent screen with test users, both scopes, both redirect URIs, then `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` | Human |
| 5 | **Push notifications haven't been checked on a real screen** | A headless browser can't click "Allow" | On the Today tab, turn on "Night before", allow notifications, then click "Send a test now". Use Chrome or Edge at `http://localhost:5173` | Human, 1 minute |
| 6 | **One test needs updating.** The smoke-test check "checkout without keys" now fails because keys exist | It's a test assumption, not an app bug | Clear the Stripe settings in that test before asserting `stripe_not_configured` (the test scripts are outside the repo; see "Verified") | Dev |
| 7 | **`VAPID_SUBJECT` is a placeholder** (`mailto:stripefit-demo@example.com`) | Push services may reject it in production | Set it to a real team email in `.env` before deploying | Dev |
| 8 | **This branch isn't merged.** `backend-complete-1` already includes `main` (the Stripe-style redesign) | Teammates on `main` won't see any of this | Open a PR at https://github.com/Asav23/StripeFit/compare/main...backend-complete-1 | Team |

**Known rough edges** (minor; fix if there's time):
- In mock mode, picks can be odd, for example a satin going-out top for a casual day. The real stylist gets the style guide and should do better. Check with `check_outfits.py` once AI is live.
- The keyword parser misses a place after a lowercase "the", as in "Debs at the Shelbourne". The AI parser handles it once AI is live.
- With a small wardrobe, "Another option" can repeat the shirt and trousers when they're the only suitable ones. That's by design: an outfit beats perfect variety.
- `PUT /api/daily/settings` replaces every field, and the frontend sends every field. Keep it that way.
- The demo weather, the demo calendar and the mock overrides reset when the API restarts.
- On Windows, if the API runs without a console window (for example from a background job), `--reload` hangs. Run it from a normal terminal, or restart it by hand.

## Frontend for the new features (built; start here to test)

The frontend is built on top of the Stripe-style redesign that was merged from `main` (commit `1d89f31`). It type-checks, builds, and was checked with screenshots at phone width (390 px) and desktop width.

| Where | What you can do |
|---|---|
| **Today tab** (new; second in the sidebar and the phone tab bar) | Switch between Today and Tomorrow. See the day's calendar events, with the one the outfit is dressed for highlighted. See the outfit (swap, wear, thumbs up or down), the packing and laundry tips, and "Another option" |
| Today → **Outfit notifications** | "Night before" and "Morning" switches, each with a time picker. A switch asks for notification permission, subscribes this browser and saves the settings. "Send a test now" pushes tomorrow's outfit straight away |
| Today → **Google Calendar** | Connect (Google consent screen, then back to `/today?calendar=connected`) or Disconnect. Shows "Demo events" when the demo calendar is on |
| Today → **My style** | Tap a colour once to love it and twice to avoid it, add a note, and save. Shows what was learned from thumbs, swaps and worn outfits |
| **Outfit cards everywhere** | "Down to X° later", the highest rain chance across the event and "from HH:MM", and labels for the new occasions |
| **AI log → Demo controls** | "Calendar used by the Today tab" presets: Interview + football, Lectures + night out, Wedding, Nothing on, Real calendar |
| **Plan tab** | Unchanged, except daily outfits no longer clutter "Recent plans" |

**A 2-minute UI test**
1. Go to AI log → Demo controls, choose **Interview + football**, then choose **Rain, 9°C**.
2. Open **Today → Tomorrow**. The outfit should be dressed for the interview, with a waterproof jacket, a "bring your sports kit" tip and the rain start time.
3. Click **Another option**, swap a piece, and give a thumbs up. Open **My style** to see that it learned something.
4. Switch on **Night before** and allow notifications, then click **Send a test now**. A "Tomorrow's outfit" notification should appear, and tapping it opens the Today tab. Use Chrome or Edge at `http://localhost:5173`.
5. Set the demo controls back to **Real forecast** and **Real calendar**.

**Not verified by machine.** Push permission prompts can't be clicked in a headless browser, so the browser subscribing and the notification appearing need one manual check (step 4). The server side of push, signing and delivery, is tested.

## What's left to do

### 1. Real AI (needs an OpenRouter key)
1. In `backend/.env`, set `OPENROUTER_API_KEY=sk-or-...` and `USE_MOCK_AI=false`.
2. Run `python scripts/check_models.py` from `backend/`. Replace any model that fails or no longer exists on OpenRouter (`python scripts/list_models.py <filter>`). Keep two fallbacks from different providers. Model names go in `.env` only.
3. Run `python scripts/check_extraction.py`. It sends each sample order email to the real model and compares the result with the expected answer. Each `DIFF` line names the field that's wrong. Tune `EXTRACT_SYSTEM` in `app/ai/prompts.py` until all 15 match. The other 3 samples are skipped before any AI call, which is correct.
4. On the Plan page, try the three example requests. Check that `used_fallback` is false, the explanation is 60 words or fewer, and it mentions the occasion and the weather.
5. Upload a few real clothing photos and one non-clothing photo. Tune `LABEL_SYSTEM` in `app/ai/prompts.py` if the labels are poor.
6. Open the AI log page (pulse icon). Tokens and cost should be filled in. Cost parsing was checked against a simulated OpenRouter response, but not a live one.

### 2. Stripe Pro purchase (keys added and verified; finish the purchase test)
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

### 3b. Google Calendar (needs the same Google OAuth client)
See "Human step: connect Google Calendar" in the daily outfit section below. Until then, use the demo calendar.

### 4. Click through the UI
Nobody has clicked through the frontend redesign (commit `90b5ed5`) yet. It type-checks and builds, and every page loads. Check that:
- every error shows a friendly message with a next step;
- every AI action shows a loading state;
- the layout works at phone width.

## Outfits that suit the event and the person

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
2. **Frontend for style, new occasion labels and whole-event weather.** Done, in the Today tab and on the outfit cards.
3. **Recording review edits as signals.** Not done yet, because they're about labels more than taste.
4. **Stage 5: actual training.** As far as we know, OpenRouter doesn't offer fine-tuning, so fine-tuning would break the "OpenRouter only" rule in `CLAUDE.md`, and that's a team decision. Today's per-user "re-ranker" is the signal-weighted scoring in `style_profile.preference_score()`. It is transparent, local, free and per user. A learned model, such as logistic regression on the exported dataset, could replace it later without touching the API.
5. **Multiple users.** Everything is keyed by `user_id` (always 1 today), so real accounts can be added without a rewrite.

## Daily outfit from your calendar, weather and laundry, sent the night before

**Goal:** every evening, tell the user what to wear tomorrow. The outfit should be dressed for what is actually on their Google Calendar, ready for tomorrow's weather across the whole day, and made only from clothes that will be clean. A morning reminder is optional.

### How a day is planned (`services/daily.py`)
1. **Calendar.** `services/google_calendar.py` reads tomorrow's events. Each event title is turned into an occasion by keywords, for example "Final interview with Accenture" becomes interview and "Five-a-side" becomes sport. Events that say nothing about clothes, such as "Dentist", are ignored.
   - The most demanding event sets the outfit, for example an interview over lectures.
   - Events that need different clothes get a packing tip, such as "Sport at 19:00: bring your sports kit and trainers."
   - With no calendar, or nothing clothes-related on it, the day is a casual day.
   - Cancelled and declined events are skipped.
2. **Weather for the whole day.** It covers the first event to the last, or 9am to 7pm, at the main event's location or the user's default location. The outfit is dressed for the coldest hour and the wettest hour, and `rain_from` says when rain starts.
3. **The normal pipeline:** rules, then the style guide, then the user's taste, then the AI stylist, then validated IDs, then the rule-based fallback.
4. **Laundry (`services/laundry.py`).**
   - **Not everything needs a wash after one wear.** A top needs washing after 1 wear, jeans after 3, and coats, shoes and accessories never go in the wash from wearing (`rules.WEARS_BEFORE_WASH`). Putting an item in the wash resets its count.
   - **The plan warns about laundry.** For example: "Wash your white oxford shirt tonight if you can: it's the best fit for tomorrow" when the right item is in the wash, "After tomorrow you'll have 1 clean top left. Put a wash on.", or a big pile waiting for the wash.
5. **Variety.** Yesterday's main pieces are avoided. "Another option" avoids everything already suggested for that day.
6. **Saved as outfits.** Daily outfits are `Outfit` rows with `kind="daily"` and `for_date`. The outfit sent last night is the one shown in the morning. If the calendar changes, it's rebuilt with the notice "Your calendar changed, so this outfit was updated." Swap, wear and feedback use the normal `/api/outfits/{id}/…` endpoints, so they also teach the taste profile and update laundry counts.

**Privacy.** The Calendar scope is `calendar.events.readonly` only. Its token is separate from Gmail's: `backend/.calendar_token.json`, gitignored. Event titles and location text are shown to the user but **never stored and never sent to the AI**. Only the occasion and the start and end times are kept. The location is used only for the weather lookup. A test confirms the titles never appear in anything stored or sent to the model.

### Notifications
- **Night before.** "Tomorrow's outfit" is sent at `evening_time`, default 20:00. For example: *"9°C, rain from 10:00. Interview 10:00, sport 19:00: white oxford shirt, navy suit trousers, black waterproof rain jacket, black leather oxford shoes, burgundy silk tie. Sport at 19:00: bring your sports kit and trainers."*
- **Morning, optional.** "Your outfit for today" is sent at `time`.
- **How they're sent.** These are real browser push notifications (Web Push with VAPID), and no extra account is needed. The keys are already in this machine's `backend/.env`; on a new machine, run `python scripts/make_vapid_keys.py` once. `services/scheduler.py` checks every minute. Each notification is sent at most once a day, and the date is recorded, so restarts never send twice. If the computer was asleep, it still sends within 3 hours. Expired subscriptions are removed. `DAILY_SCHEDULER_ENABLED=false` turns the scheduler off. Set `VAPID_SUBJECT` to a real team address before any deployment.

### Demo without Google
`POST /api/debug/demo-calendar` pretends the calendar has these events, on any day:

```json
{"events": [{"title": "Interview", "start": "10:00", "end": "11:00", "location": "Grand Canal Dock"},
            {"title": "Football", "start": "19:00", "end": "20:00"}]}
```

Send `{"events": null}` to switch back to the real calendar. Combine it with the rain demo weather to show the full night-before message.

### API

| Method and path | What it does |
|---|---|
| `GET /api/daily?day=today\|tomorrow` | `{day, outfit, events, settings}`. Built on first request or by the scheduler, and rebuilt if the calendar changed |
| `POST /api/daily/another?day=…` | A different outfit for that day |
| `GET /api/daily/settings` | `{enabled, time, location, evening_enabled, evening_time, push_configured, subscriptions, last_sent_date, evening_last_sent, calendar_connected}` |
| `PUT /api/daily/settings` | Body `{enabled, time, location, evening_enabled, evening_time}`. This is a full replace, so send every field. Times are "HH:MM" in Dublin time |
| `GET /api/calendar/status` | `{configured, connected, demo}` |
| `GET /api/calendar/auth-url` | The Google consent link. The callback is `/api/calendar/callback`, which redirects to `/today?calendar=connected\|cancelled\|error` |
| `POST /api/calendar/disconnect` | Deletes the token |
| `GET /api/calendar/events?day=tomorrow` | The events as the planner sees them, with titles, for the owner only |
| `GET /api/push/config` | `{configured, public_key}` |
| `POST /api/push/subscribe` | Body is the browser's `PushSubscription.toJSON()` |
| `POST /api/push/unsubscribe` | Body `{endpoint}` |
| `POST /api/push/test` | Sends tomorrow's outfit notification now |
| `GET/POST /api/debug/demo-calendar` | The demo events (see above) |

### Human step: connect Google Calendar
This uses the same Google Cloud project and OAuth client as Gmail, in step 3 above.
1. In Google Cloud Console, go to **APIs & Services → Library** and enable the **Google Calendar API**.
2. On the **OAuth consent screen**, add the scope `.../auth/calendar.events.readonly`.
3. Under **Credentials**, open the web OAuth client and add the authorised redirect URI `http://localhost:8000/api/calendar/callback`.
4. Make sure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are in `backend/.env`, and restart the API.
5. Open the link from `GET /api/calendar/auth-url` and approve. Once the frontend exists, this will be a "Connect Google Calendar" button.

### Verified (mock mode, no Google account)
- **Planning a day.** With no calendar, the plan is a casual day with 10-hour weather. With the demo calendar (interview, football and a dentist), the outfit is dressed for the interview with a football packing tip and weather from 10:00 to 20:30 at Grand Canal Dock. A dentist-only day is casual. Changing the calendar rebuilds the outfit.
- **Privacy.** Titles and location text never reach stored outfits or the AI.
- **Laundry.** A top goes in the wash after 1 wear, jeans after 3, and a coat never does. Washing resets the count. The plan says "wash your shirt tonight" and "low on clean tops".
- **Night-before notification.** Not due at 19:30, sent at 20:05, and only once. The message contains the weather with the rain start time, the plan, the items and the packing tip. The next morning shows the same outfit.
- **Real Google event parsing.** Cancelled and declined events are skipped, UTC times are converted to Dublin time, and all-day events are handled.
- **OAuth.** The scope is calendar read-only only, with PKCE and the correct redirect URI. A forged state or a cancelled sign-in redirects safely.
- **Not tested.** A real Google account, which needs the human step above.

### Frontend
Built: see "Frontend for the new features" at the top of this file.

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
| Daily outfit, scheduler and Web Push notifications (night before + morning) | `services/daily.py`, `services/scheduler.py`, `services/push.py`, `routers/daily.py`, `routers/push.py` |
| Google Calendar (read-only) day planning, demo calendar | `services/google_calendar.py`, `routers/google_calendar.py`, `services/daily.py` |
| Laundry: wears before washing, "wash it tonight" and low-on-clean tips | `services/laundry.py`, `rules.WEARS_BEFORE_WASH` |
| Outfit scenario checker, dataset export, VAPID key script | `scripts/check_outfits.py`, `scripts/export_style_dataset.py`, `scripts/make_vapid_keys.py` |

API change: `POST /api/ingest/email` and `POST /api/ingest/samples` now return `202` with a job. Poll `GET /api/ingest/jobs/{id}` for progress and the summary. The frontend is already updated.

## Verified (mock AI mode)
- **Calendar, night-before and laundry: 46 of 46 checks passed.**
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
