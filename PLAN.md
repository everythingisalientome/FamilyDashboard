# PLAN — Family Wall Dashboard

Status legend: [ ] not started · [~] in progress · [x] done

---

## Phase 1 — Skeleton shell  [x]

**Goal:** A working dashboard page served from this server that the Pi can
display, with layout and photos but placeholder data.

**Build:**
- FastAPI app in `app/main.py` serving `static/` at `/` and mounting `/api`.
- `static/index.html` + CSS grid layout with named regions:
  - left column (~40%): photo slideshow, full height
  - top right: clock + date (large, readable across a room)
  - middle right: calendar/agenda area (placeholder)
  - bottom right: weather area (placeholder)
  - top strip (full width, hidden by default): alert banner
- Clock renders locally in JS (updates every second, 12-hour format).
- Photo slideshow: `GET /api/photos` returns the file list from `photos/`;
  JS crossfades between them every 60 s. Handle portrait and landscape.
- Nightly self-reload: at 03:00 local, JS calls `location.reload()`.
- Target resolution: 1920×1080 landscape. No scrollbars, no cursor
  dependence, dark background (it's on a wall at night).

**Done when:** Opening `http://<server-ip>:8000/` full-screen shows clock,
date, and rotating photos with the final layout regions visible.

**Verified 2026-08-02** in Chromium at a forced 1920×1080 layout box: clock,
date, both placeholder panels and the crossfading slideshow all render; no
scroll on either axis; console clean apart from the reload notice. Measured
regions — photos 750×1036 (39%, full height), clock 1104×275, agenda
1104×378, weather 1104×339 (275+378+339+2×22 gap = 1036). Un-hiding the
banner reflows every region with no overflow. Portrait and landscape test
images both display whole against their blurred self-fill.

**Deviations from spec** (all additive — nothing in the spec was dropped):
- Added `GET /api/settings`, not in the spec. Serves timezone, photo
  interval, list-refresh interval and reload hour so `config.py` stays the
  single source of truth; `main.js` falls back to hardcoded defaults if the
  call fails.
- Added `GET /healthz` for a cheap liveness check (useful for NSSM later).
- Photo list re-fetches every 30 min (`PHOTO_LIST_REFRESH_SECONDS`) so new
  drops appear without a restart. Not required by the spec.
- Photo URLs carry a `?v=<size>` cache-buster, and a photo that fails to
  load is skipped rather than freezing the slideshow.
- Clock ticks every second but displays `h:mm` only — no seconds digit, on
  the grounds that it reads better from across a room.
- `style.css` uses `:has()` for the no-banner padding fix. Confirmed
  supported in the test browser; re-check on the Pi's Chromium build.
- `requirements.txt` pins only fastapi + uvicorn. APScheduler, httpx,
  icalendar and BeautifulSoup4 land in Phase 2 when first used.
- No SQLite yet — Phase 1 caches nothing, so `data/` is still empty.

---

## Phase 2 — Calendars & weather  [x]

**Goal:** Replicate everything the old wall display provided: real events and forecast.

**Data sources (initial):** every ICS feed is a capability URL, so all of them
live in `.env` (see `.env.example`), never in `config.py`. Feeds are discovered
by scanning the environment for `CAL_<KEY>_URL` — adding another calendar is
three lines in `.env` plus a restart, with no code change.
- Trash collection (ReCollect ICS) — `CAL_TRASH_URL`.
- Cabarrus County Schools ICS — `CAL_SCHOOL_URL`.
- Family Google Calendar via its "secret address in iCal format" URL —
  `CAL_FAMILY_URL` (read-only, no OAuth; blank until generated, then skipped).
- Weather: NWS API (api.weather.gov) for Harrisburg, NC — current
  conditions, 4-day forecast, and precipitation chances. No API key needed.

**Build:**
- `fetchers/calendars.py`: fetch all configured ICS URLs every 4 h, expand
  events for the next 30 days (handle all-day events and recurrence rules),
  merge with a `source` tag per feed, store in SQLite.
- `fetchers/weather.py`: fetch every 30 min, store current + daily forecast.
- `GET /api/events?days=N` and `GET /api/weather` per the JSON envelope
  convention.
- Frontend: month-grid calendar with event dots/titles on their days plus a
  compact "next 5 upcoming" agenda list; weather widget mirroring the old
  old layout (current temp + feels-like, 4-day outlook with highs/lows
  and precip %).
- Per-source display colors (school vs trash vs family).

**Done when:** Real school events, trash pickup days, and live weather render
on the wall with no manual refresh, and unplugging the internet leaves the
last data visible rather than breaking the page.

**Verified 2026-08-02** against the live feeds, at a forced 1920×1080 layout
box. Cold start from an empty `data/` fills the cache through APScheduler
inside the FastAPI process: 4 school events, 6 trash pickups, 7 forecast days
and a current observation from KJQF. Regions — photos 750×1036, clock 1104×198,
calendar 1104×431, agenda 1104×127, weather 1104×213 (198+431+127+213+3×22 gap
= 1036). No scroll on either axis; console clean apart from the reload notice.

Offline behaviour tested both ways. Pointing every feed at an unroutable host:
neither `run()` raised, all cached rows survived untouched, each job recorded
its error while keeping `last_success_utc`. Rejecting `fetch()` in the page:
month grid, agenda, temperature and forecast all unchanged, nothing blanked.

Banner reflow re-checked (Phase 3 will need it): un-hiding it keeps all 9
chips unclipped and the clock inside its row, with no overflow anywhere.

**Deviations from spec** (all additive unless noted):
- **Two dependencies beyond the stack list.** `recurring-ical-events` does the
  RRULE/EXDATE/RECURRENCE-ID expansion — it is built on `icalendar`, and
  hand-rolling recurrence is where ICS handling usually goes wrong.
  `python-dotenv` reads `.env`.
- **All feed URLs moved to `.env`; feeds are now env-discovered.** Originally
  the school and trash URLs were hardcoded in `config.py` and only the family
  URL came from `.env`. Every ICS URL is a capability URL, so all three now
  live in `.env`. `config.py` no longer enumerates feeds at all: it scans the
  environment for `CAL_<KEY>_URL` (with optional `CAL_<KEY>_LABEL`, `_COLOR`,
  `_ORDER`) and builds one `CalendarFeed` per match. Adding a calendar tomorrow
  is three lines in `.env` and a restart — no code edit — which is exactly what
  the Phase 5 admin page will write. Colours default from a palette (skipping
  any already used) when unset; feeds with a blank URL are skipped. The legacy
  `FAMILY_CALENDAR_ICS_URL` is still honoured as a fallback.
- **The family Google Calendar is not configured yet.** `CAL_FAMILY_URL` in
  `.env` is blank, so that feed is skipped; the family label/colour/order are
  pre-seeded in `.env.example`, so filling the URL and restarting is all that
  is needed.
- **Clock (time + date) moved off the right column onto the photos.** It was a
  dedicated grid row above the calendar; it is now a transparent overlay in the
  photo column's top-left (a soft top-down scrim keeps it legible over bright
  photos, `pointer-events: none`). The freed row went to the month grid, so the
  calendar is now the top-to-agenda height of the right column and its day cells
  are noticeably larger. The right column is three `fr` rows (calendar, agenda,
  weather) instead of four. Digits size with `clamp(...vw...)` now that they no
  longer live in a sized container. Supersedes the region measurements in the
  Phase 2 verification note above.
- **All weather/polling tunables moved to `.env`.** `WEATHER_LAT`, `WEATHER_LON`,
  `NWS_USER_AGENT`, `WEATHER_REFRESH_SECONDS`, `FORECAST_DAYS`,
  `DATA_REFRESH_SECONDS` and `FETCH_TIMEOUT_SECONDS` are now read from the
  environment via small `_env_int/_float/_str` helpers, with the old hardcoded
  values as fallbacks. `config.py` still names each setting (single source of
  truth); `.env`/`.env.example` are where they change. A blank or unparseable
  value falls back to the default rather than crashing on boot.
- **Calendars refresh nightly on a wall-clock schedule, not a 4 h interval.**
  `CALENDAR_REFRESH_SECONDS` is gone; the calendar job now uses an APScheduler
  `CronTrigger` (default every day 23:00 **local** — `CALENDAR_REFRESH_DAY/HOUR/
  MINUTE` in `.env`, where `DAY=*` is nightly and a weekday name pins it to
  weekly) while weather stays on its interval. `next_run_time` still forces one
  run ~2 s after boot, so a restart (e.g. after adding a feed) fetches
  immediately instead of waiting for the night. The scheduler keeps its UTC
  clock but the cron trigger carries `DISPLAY_TZ`, so "23:00" is Eastern.
- **Weather panel enlarged for across-the-room legibility.** Current temp,
  condition, and every forecast card (label, icon, hi/lo, precip) were bumped up
  and the weather row given more height (taken from the very tall month grid).
  The current-conditions line uses `pre-wrap` so Feels/H/L/hum wraps rather than
  clipping at the forecast edge. The forecast strip is now `grid-auto-flow:
  column` so it lays out whatever `FORECAST_DAYS` asks for instead of a
  hardcoded four columns.
- **Google Photos shared-album sync (pulls the "Photo source upgrade" backlog
  item forward).** New `fetchers/photos.py` scrapes a *public* "anyone with the
  link" album page (no Google login), downloads each image into `photos/` at a
  bounded size behind a `gphoto_` prefix, and prunes its own stale downloads;
  the existing `/api/photos` + slideshow then show them with no other change.
  All config is in `.env`: `PHOTOS_ALBUM_URL` (blank = disabled),
  `PHOTO_SYNC_REFRESH_SECONDS` (default hourly), `PHOTO_SYNC_MAX`,
  `PHOTO_SYNC_WIDTH/HEIGHT`. The job is only scheduled when the URL is set, runs
  on the same boot-kick + interval as weather, and is serve-stale: a failed sync
  or one that finds no photos (e.g. the link is not public) leaves the current
  photos on the wall. Manual drops into `photos/` are never touched (only the
  `gphoto_` prefix is pruned). A private album would need OAuth + the Google
  Photos API, which the no-auth principle rules out, so only public links work.
- **Display tuning after seeing it on the wall.** The clock overlay is now one
  compact line ("6:44pm Sunday, Aug 2" — lowercase meridiem against the time,
  short month) instead of a large stacked block. The weather panel and its
  fonts were dialled back down (they had been pushed too large) and the row
  re-balanced; the agenda type is smaller and clamps at three lines so long
  titles ("HHW Collection · Yard Waste · …") stop truncating. Slideshow pacing
  is faster and now env-driven: `PHOTO_INTERVAL_SECONDS` (default 10 s, was 60)
  and `PHOTO_LIST_REFRESH_SECONDS`.
- **Keyword event categories colour events beyond their feed.** `event_styles.py`
  matches each event title (server-side, word-boundary, plural-tolerant) against
  keyword categories and the events API tags every event with its `category`;
  `calendar.js` then paints the chip / agenda entry in the category colour and
  tints the day cell. Three ship by default — **holiday** (red), **school**
  (golden-orange: first/last day, early dismissal), **quarter** (purple: end of
  quarter) — and all are tunable in `.env` via `EVENT_STYLE_<KEY>_KEYWORDS`
  (appended to the built-ins), `_COLOR`, `_ORDER` (lower wins on overlap); a new
  `<KEY>` with keywords+colour defines a new category. Location-specific terms
  (Cabarrus's "Capped/Uncapped Workdays") live in `.env`. Matching is server-side
  per the "Pi stays dumb" rule; the plural `s?` in the regex is what makes
  "workday" catch "Capped Workdays".
- **Multi-day spans read as one block.** Events are already fanned across every
  covered day (`ics.py` fixes the exclusive all-day DTEND to an inclusive end,
  `bucketByDate` fans them out), so a categorised multi-day event now tints its
  whole run of cells one colour — a break week shows as a continuous red band
  rather than seven unrelated chips. The cell takes the highest-precedence
  category present when a day has more than one.
- **Weather current block rebuilt + enriched.** Four compact lines now: temp
  with Celsius in brackets and the condition inline (`77°(25°C) - Partly
  Cloudy`); Feels/Low; Humidity/UV/Wind; Sunset/moon-phase. The panel is smaller
  than the previous over-large pass. **New provider (deviation from the
  NWS-only stack):** NWS serves no UV index or sun times, so a `weather:astro`
  job pulls `uv_index_max` + sunrise/sunset from **Open-Meteo** (keyless, one
  call, cached in a new `weather_astro` table) — isolated so its outage can't
  touch the NWS temperature/forecast jobs. Moon phase is computed locally in the
  API from the synodic month (no network, no dependency). Celsius is converted
  client-side. Moon glyph is an emoji; if the Pi's Chromium lacks colour emoji
  it degrades to the phase name, which is still shown.
- **Upcoming highlights ticker.** A one-line, non-scrolling strip between the
  agenda and weather (its own grid row) lists the `HIGHLIGHT_KEYWORDS` (`.env`)
  that appear in an event title within the next `HIGHLIGHT_DAYS` (default 7),
  as "MonDay: Keyword" — it shows the matched *keyword* title-cased, not the
  full event title (so "…· Recycling · Garbage" reads simply as "Recycling").
  Computed server-side in `/api/events` (`highlights`) and rendered by
  `calendar.js` off the same poll — no extra fetch. The strip clips rather than
  scrolls; styled with an indigo→teal gradient and an "UPCOMING" pill. A
  lightweight, calendar-sourced precursor to the Phase 3 alerts banner.
- **Outlook strip drops today.** `FORECAST_DAYS` now means what its comment
  always said — days *not counting today*. The weather API fetches today plus N
  days, still uses today's row to enrich the current-conditions block (low,
  condition fallback), but the forecast cards start at tomorrow since today is
  already the big number above them.
- **Clock is smaller than Phase 1.** It had a `13vw`/`13rem` clamp; the month
  grid needs the height, so the digits now size off the clock row itself with
  `min(10rem, 78cqh)` and the row is ~198px instead of 275px. Sizing from the
  container also means Phase 3's banner shrinks the digits rather than pushing
  them into the calendar. Uses container queries — same Chromium-version ask
  as the `:has()` already relied on. Say if it reads too small on the wall.
- All four right-hand rows are `fr`, not fixed percentages, so the banner's
  height is taken from every region proportionally. With percentages it came
  entirely out of the month grid, which squeezed the day cells below the
  height of one event chip and blanked every title exactly when a severe
  weather alert was showing.
- How many events fit in a day cell is measured after layout rather than
  fixed, and the overflow count sits beside the date as a small `+N` instead
  of eating a chip's worth of vertical space. A 6-week month fits one chip per
  cell, a 5-week month two; the agenda strip carries the next five in full.
- Weather icons are hand-drawn SVG symbols in `index.html`, not NWS's icon
  URLs, since the page may not call external services. `nws_icons.py` maps NWS
  condition tokens onto the 12 local glyphs. Note the CSS selectors for glyph
  internals must not use a descendant combinator — `<use>` puts them in a
  shadow tree that `.wx-icon .wx-bolt` cannot reach.
- Current conditions walk the four nearest stations until one reports a
  temperature (KJQF often returns a reading with no condition text at all),
  and fall back to today's forecast for the condition and icon.
- ReCollect's generated pickup titles ("Yard waste - concord, bulky waste -
  concord, and garbage - concord") are compacted to "Yard Waste · Bulky Waste
  · Garbage" — the raw form is far too long for a 147px cell.
- `?days=N` also reaches back to the start of the current month grid, since
  the display draws the whole month and its earlier days would be blank.
- Weather is two jobs (`weather:current`, `weather:forecast`), not one, so a
  dead station does not blank the forecast.
- Added `DATA_REFRESH_SECONDS` (5 min) to `/api/settings` for the page's poll
  interval; it reads cached rows, unrelated to the fetch intervals.
- `fetch_meta` records last attempt/success/error per job — more than Phase 2
  needs, but it is what the Phase 5 admin page and stale-dot will read.
- Split for the ~200-line rule: `fetchers/nws.py` (NWS protocol) out of
  `weather.py`, `static/js/dates.js` out of `calendar.js`, and `style.css`
  into `style.css` + `calendar.css` + `weather.css`.

---

## Phase 3 — Alerts engine  [x]

**Goal:** The display gets loud when something needs attention (the thing
the old service couldn't do).

**Already in place from Phase 2** (reuse, don't rebuild):
- Keyword matching against event titles already exists in `event_styles.py`
  (categories: holiday/school/quarter) — the closure/early-dismissal *detection*
  the banner needs is done; Phase 3 adds the banner rendering on top of it.
- The banner region (`#banner`) and its reflow are already wired in the layout.
- The highlights ticker (`HIGHLIGHT_KEYWORDS`) is a calendar-sourced upcoming
  strip — a lightweight precursor, not the alert engine.

**Build:**
- `fetchers/alerts.py`: poll NWS active alerts for the county every 10 min.
- Rule-based reminders evaluated on the server:
  - trash/recycling event tomorrow → reminder chip from 5 pm the evening before
  - school closure/early-dismissal events → prominent banner (feed the existing
    `event_styles` matcher, don't write a second keyword list)
  - configurable countdown chips (birthdays, events) defined in `config.py`
- `GET /api/alerts` returning active alerts sorted by severity.
- Frontend: red full-width banner for severe weather / closures; smaller
  amber chips for reminders. Banner overrides normal layout height.

**Done when:** A test NWS alert and a fake "trash tomorrow" both render
correctly, and expired alerts disappear on their own.

**Verified 2026-08-02** at a forced 1920×1080 layout box, over three passes as
the household reacted to it on the wall: (1) alert set + rules as a top banner;
(2) rejected — the banner pushed the whole dashboard down — so moved to a
photo-panel overlay; (3) rejected again for showing everything at once in big
bold multi-line blocks, so reworked to a **single shiny pill that rotates
through the alerts one at a time**, single-line, smaller/lighter type. Final
design verified: the live NWS fetcher runs clean against `api.weather.gov` (0
active alerts for Harrisburg, fetch recorded success). With test rows injected,
`/api/alerts` returned a red "Severe Thunderstorm Warning" (+ its NWS headline),
a gold "Heat Advisory", a gold "Trash tomorrow · Recycling · Garbage" (shown
because the clock was past 5 pm), and a custom-purple "Ava's Birthday" from an
alert-flagged calendar. A non-qualifying "Air Quality Alert" and an `expires`-in-
the-past "Flood Warning" were both dropped; a "Tornado Warning" (not in the
keyword list) still came through red via the severity safety net. The overlay
rendered **one pill at a time**, rotating red → gold → gold → custom every
`ALERT_ROTATE_SECONDS`; the pill was a single line (measured height < 48 px),
title 19 px / weight 600 (down from 26 px / 700), a shiny gradient per tone, and
wholly inside the photo panel — the calendar still started at the top gap
(13 px), i.e. **the dashboard was not pushed down**, no scroll on either axis.
Clearing the cache faded it out. Console clean apart from the reload notice (and
a pre-existing favicon 404).

**Deviations from spec** (all additive unless noted):
- **Display redesigned from a top banner to a photo-panel overlay** (supersedes
  the spec's "red full-width banner … overrides normal layout height"). The
  banner was rejected on the wall for pushing every region down. Alerts now
  float over the bottom of the photo column — the mirror of the clock over the
  top — on a bottom-up scrim, `pointer-events:none`, so they take **no grid row
  and never reflow anything**. The old `#banner` row, its `grid-template-areas`
  entry and the `:has(.banner[hidden])` padding fix were all removed.
- **One shiny pill at a time, rotating, single line.** Rather than stacking every
  alert at once (rejected as cluttered and too loud), the overlay shows a single
  pill and rotates through the active alerts one at a time, each on screen for
  `ALERT_ROTATE_SECONDS` (7) before crossfading to the next. Each is one line
  (title · text, ellipsised) in smaller, lighter type, and a glossy gradient with
  a gentle brightness pulse (`alert-shine`) rather than an opacity blink. The
  strip still fades in for `ALERT_SHOW_SECONDS` (60) once every
  `ALERT_CYCLE_SECONDS` (1800) — 1 min in view every 30 — all three `.env`-tunable
  and sent to the page via `/api/settings`. `prefers-reduced-motion` drops the
  animation.
- **Per-alert tone, not banner/chip levels.** Every record carries a `tone` —
  `red` (closures + NWS warnings: severity in `ALERT_RED_SEVERITIES` or "warning"
  in the event name), `gold` (advisories / watches, e.g. Heat Advisory, + trash),
  or `custom` (a calendar's own colour). Red and gold are shiny gradients styled
  in `alerts.css`; `custom` builds a gradient from the feed's hex. The earlier
  `ALERT_BANNER_SEVERITIES` / `ALERT_COLOR_*` model is gone.
- **NWS alerts are filtered, with a safety net.** Only alerts whose event name
  matches `ALERT_WEATHER_KEYWORDS` (default thunderstorm, lightning, heat
  advisory) show — but any alert at `ALERT_SAFETY_SEVERITIES` (Extreme/Severe)
  qualifies too, so a Tornado / Flash Flood Warning is never silently hidden.
  (The household asked for a short list; the safety net keeps a real emergency
  from being suppressed.)
- **Two families, derived vs fetched** (kept from the first pass). NWS alerts are
  fetched: `fetchers/alerts.py` polls `/alerts/active?point=<WEATHER_LAT>,<LON>`
  every 10 min (reusing `nws.get()` and the configured point — no separate
  county/zone), replace-all into a new `weather_alerts` table, serve-stale via
  `record_*`. Closures, trash and per-calendar alerts need **no fetcher and no
  table** — they are *derived at request time* in `/api/alerts` from the events
  cache via a new `alert_rules.py` (pure functions), the way `_highlights` is
  derived in `/api/events`. **Read-time expiry** is retained: `/api/alerts` drops
  any alert past its `expires`/`ends` (preferring the later of the two), so an
  expiring warning vanishes on the next 5-min page poll, not only at the next
  fetch.
- **Closures fire on any weekday they cover, not first-day-only.** With the gentle
  overlay (vs the loud banner) it is useful to show "No School" on each weekday of
  a break, so the rule became "closure event covers today AND today is a weekday"
  (weekend days are skipped — no-school is trivially true then). Still reuses
  `event_styles.categorize` — **no second keyword list** — with
  `CLOSURE_ALERT_CATEGORIES` (default `school, holiday`) picking the categories.
- **Per-calendar alert colour.** A new `CAL_<KEY>_ALERT_COLOR` on any feed makes
  every event from that feed covering today raise an alert in that colour — so a
  "Birthdays" calendar can light the wall up on the day, configured entirely in
  `.env` (mirrors "configure a calendar to show alerts with a colour").
- **Countdown chips dropped.** The household asked for only the listed alert
  types, so the `COUNTDOWN_<KEY>_*` mechanism from the first pass was removed
  (config, rules and `.env` docs) — the per-calendar alert colour covers the
  birthday case instead.
- **Trash reminder** (kept): a pickup today always shows; tomorrow's shows once
  the local clock passes `TRASH_REMINDER_HOUR` (5 pm). Matched by
  `TRASH_REMINDER_KEYWORDS`, source-agnostic; always yellow.
- **New `static/js/alerts.js` + `static/css/alerts.css`**; `main.js` wires
  `startAlerts`; `/api/settings` now also carries the two alert timings. Alerts
  are polled on the shared `DATA_REFRESH_SECONDS`; the NWS *fetch* stays 10 min.

---

## Phase 4 — Photo → calendar: Google Calendar feed + JSON importer  [x]

**Goal:** Family events (doctor visits, daycare closures, trips, parties,
reminders) get onto the wall and onto everyone's phones with the least typing.
Anyone in the house photographs the source — a daycare year calendar, an
appointment email — pastes it into any chat model with the prompt in
`docs/event-extraction-prompt.md`, and pastes the JSON it returns into an admin
tab. The server validates it, shows it for review, and writes it to the family
Google Calendar. **No model API is called by this app** — the LLM step is a
human-in-the-loop paste, which is also the review step.

**Decided (2026-10-18), supersedes the original "scrape + LLM" spec:**
- **Source:** the family Google Calendar, not a scraped web page. The original
  spec's scraper/LLM/schema-validation idea survives as the extraction prompt +
  server-side schema validation; the "LLM call from the server" part is gone.
- **Google Calendar is the single source of truth** for family events — not a
  local `manual` table. Everything the importer writes is visible and editable
  on every phone; nothing lives only on the wall. Verified 2026-10-18: a
  **service account** (`family-wall-calendar@…iam.gserviceaccount.com`) with the
  calendar shared to it as *Make changes to events* can list and insert events
  from Python with scope `calendar.events` only — no OAuth consent flow, no
  token expiry (`scripts/test_calendar.py`).
- **Read the family calendar through the API, not its secret ICS URL.** The ICS
  endpoint is cached by Google for hours; the API is immediate, so paste →
  insert → refresh → on the wall at the next poll. School and trash stay ICS.
- **One calendar, one account.** The household wants everything editable in one
  place. Person attribution is a tag on the event, not a separate calendar.

**Config (`.env`):**
- `GCAL_CALENDAR_ID` — the explicit calendar id from *Integrate calendar*
  (never `primary`: for a service account that is its own empty calendar).
- `GCAL_SERVICE_ACCOUNT_FILE` — default `data/gcal-sa.json` (git-ignored,
  outside `static/`). Move the key out of Downloads.
- `CAL_FAMILY_URL` is retired; the family feed key stays `family` so colours,
  ordering and `fetch_meta` rows carry over.

**Build:**
- `fetchers/gcal.py` — one `run()` like every other fetcher: `events.list` with
  `timeMin` = start of the current month grid, `timeMax` = today + 30 d,
  `singleEvents=true`, `orderBy=startTime`, `timeZone=America/New_York`; maps
  each item onto the existing `events` row shape with `source='family'`; carries
  `extendedProperties.private.person/kind` through as new columns `person`,
  `kind`; replace-all per source, `record_*` serve-stale like the ICS feeds.
  Scheduled on the same nightly cron + boot kick as calendars, plus the
  importer fires it after every write. Gmail-created events
  (`eventType: fromGmail`) are kept — they are real appointments.
- Dependencies: `google-api-python-client`, `google-auth` (+ `tzdata` on
  Windows). Documented in `deployment.md` with the service-account setup steps
  and `scripts/test_calendar.py` (parametrised from `.env`) as the verification.
- `app/gcal_writer.py` — `insert(events)` / `delete(id)`. Deterministic ids
  (`wall<sha1(person|date|title)[:24]>`, base32-safe) so re-pasting the same
  JSON is a no-op, not duplicates; `extendedProperties.private = {source:
  'wall', person, kind}`; `summary` built as `<Title>` (the person lives in the
  tag, and the name-in-title matcher is only the fallback for hand-entered
  events); `location`/`description` from the JSON; `reminders.useDefault=false`.
- `app/api/importer.py` — `POST /api/admin/import/validate` (JSON array in →
  per-row `ok|error` with reasons: schema, date parse, outside ±18 months,
  duplicate id already on the calendar, `supersedes` match found) and
  `POST /api/admin/import/commit` (the reviewed rows → writer → fetch → result).
  Past-dated rows default to unchecked. Invalid rows never reach Google.
- Admin "Add events" tab, **phone-sized** (the current admin table is desktop
  only): person picker, paste box, Validate → editable review table (date,
  time, title, person, kind, include ✓, "replaces <old>" ✓) → Add to calendar
  → result. Opened from a phone on the home Wi-Fi.
- `docs/event-extraction-prompt.md` — the prompt (schema, rules, two worked
  examples from the Kiddie Academy 2026 calendar and a rescheduled well-child
  email). The importer's validator and the prompt share one contract.
- Title conventions the extractor produces and the dashboard relies on:
  `kind=closed` → title keeps the reason ("Daycare closed – Thanksgiving") and
  `closed` is added to `EVENT_STYLE_HOLIDAY_KEYWORDS`, so a daycare closure is
  a holiday on the wall; `kind=early_close` → "Closes 12:00 – Family Luncheon"
  with `early dismissal`/`closes` in the school (dismissal) keywords.

**Done when:** the Kiddie Academy 2026 page and one appointment screenshot go
photo → prompt → paste → calendar from a phone in under two minutes, the wall
shows them at the next poll, a second paste of the same JSON adds nothing, and
a rescheduled appointment replaces its predecessor.

**Known boundary:** the importer is the first thing on `/admin` that writes
outside the house. It stays LAN-only / no-auth per the one-household model; the
service-account key grants *events only* on *one* calendar.

**Step 1 done (2026-10-18) — Google Calendar feed, read-only.** Verified on a
dev server with the real key: boot + `POST /api/admin/refresh/calendars` log
`Calendar family: 2 events through 2026-11-17`, `/api/admin/status` shows
`events:family` (source = the calendar id, 26 h window, no error), and
`/api/events` + `/v2` show the two Oct 19 10:00 test events on the family line
and grid (untagged, no name in the title → *Family*). No writer, importer or
admin tab yet.
- `app/fetchers/gcal.py` — `run()` builds the service from
  `GCAL_SERVICE_ACCOUNT_FILE` (scope `calendar.events`), `events.list` over the
  grid window (`singleEvents`, `orderBy=startTime`, `timeZone=DISPLAY_TZ_NAME`,
  250/page, follows `nextPageToken`, max 20 pages), skips `cancelled`, keeps
  `fromGmail`, maps `extendedProperties.private.person` (lowercased) / `kind`
  onto the `person`/`kind` columns, replace-all for `family` + `record_*`.
  Missing key file or blank id → `record_failure`, rows untouched.
- **Timeout:** `httplib2.Http(timeout=FETCH_TIMEOUT_SECONDS)` inside
  `google_auth_httplib2.AuthorizedHttp`, not a process-wide socket default.
  `google-auth-httplib2` + `httplib2` are now pinned in requirements.txt (they
  were already transitive deps). The Google imports are lazy, so a deploy that
  skipped `pip install` still boots and only this feed records the error.
- **Config:** `GCAL_CALENDAR_ID`, `GCAL_SERVICE_ACCOUNT_FILE` (default
  `data/gcal-sa.json`, relative paths from the repo root). When the id is set,
  `family` is added to `CALENDAR_FEEDS` with `url=""` and the existing
  `CAL_FAMILY_*` label/colour/order; the ICS fetcher skips blank-url feeds.
  `CAL_FAMILY_URL` *and* the older `FAMILY_CALENDAR_ICS_URL` are always
  ignored now (warning logged at scheduler start if set).
- **Shared code (deviation):** `grid_start` moved to a new `app/event_window.py`
  (+ `fetch_window`), used by both fetchers and `/api/events`. The ICS date
  math was extracted to `ics.time_fields()` and reused by gcal, so the
  exclusive all-day end and midnight-end rules are one implementation.
  `calendars.replace_source` is public and writes `person`/`kind`.
- **Scheduler/admin:** job `gcal` on the calendars `CronTrigger` + boot kick,
  only when configured. Refresh *calendars* runs ICS then gcal. The log
  endpoints moved out of `admin.py` into `app/api/admin_logs.py` (deviation, to
  keep admin.py under ~200 lines).
- `scripts/test_calendar.py` reads `.env` via `app.config`; read-only by
  default, `--write` inserts and immediately deletes a test event (the old
  script left one behind on every run — the Oct 19 test events came from it).
- v2 hero: an empty `persons` roster renders "No people configured — add
  PERSON_<KEY>_LABEL to .env" instead of a blank gold block.
- Tests: `tests/test_gcal.py` (fake two-page service, row mapping, exclusive
  end, UTC, paging, failure paths, person/family attribution, config feed
  injection, ICS skip). 36 tests pass.

**Step 2 done (2026-10-18) — writer, importer, admin "Add events", exclusions.**
- `app/gcal_client.py` — `build_service()` / `config_problem()` /
  `http_status()` moved out of `fetchers/gcal.py`, shared with the writer.
- `app/gcal_writer.py` — `event_id`, `to_google` (all-day exclusive end;
  timed with the DISPLAY_TZ offset + `timeZone`, default 1 h when no
  end_time; `extendedProperties.private = {source: wall, person, kind}`;
  `reminders.useDefault=false`; description = notes), `insert_many`
  (`sendUpdates=none`; 409 → `exists`), `delete` (looks the event up first;
  raises `PermissionError` unless `source == wall`; missing/cancelled →
  False), `list_wall` (`privateExtendedProperty=source=wall`, paged) and
  `find_supersedes` (same person + title on the old date; `start_time` breaks
  ties).
- `app/importer_rules.py` — the pure validator: required keys, enums,
  date/time formats, ±18 months, `end_date >= date`, person from the row →
  the request → error `no person` (must be a roster key or `family`), title
  non-empty and ≤ 80 after the title conventions. `past`, warnings for low
  confidence / ignored times / a `supersedes` with no old date, and
  `{"skipped": …}` objects come back as error rows. Error rows are returned
  with whatever parsed, never dropped.
- `app/api/importer.py` — `POST /api/admin/import/validate` (one
  `list_wall` over every row's span, incl. superseded dates, per request) and
  `POST /api/admin/import/commit` (re-validates every row server-side, then
  `insert_many`, then `delete` per id, then `gcal.run()` on a daemon thread;
  returns `{created, exists, errors, deleted, results}`). 503 when the
  calendar isn't configured.
- Admin: `static/admin.html` + `js/admin_import.js` + `css/admin_import.css`.
  "Add events" is the first section: person select (`/api/events.persons` +
  Family), paste box (a markdown fence or prose around the array is
  tolerated), Validate, review rows (tick · editable date · time · editable
  title · person · kind · status chip; past unticked, error/exists locked;
  "replaces <date> — delete old"), "Add N events to calendar", a result line,
  and the textarea is cleared. Under 700 px each row is a stacked card; 44 px
  targets, 16 px inputs. `admin.css`: the status table scrolls inside its
  own box on a phone, so the page no longer scrolls sideways.
- **Exclusions:** `EVENT_EXCLUDE_KEYWORDS` (display.py, `.env.example`,
  `.env`; default `board of education, school bond, community forum, futures
  fair`) is a case-insensitive substring match, applied once in
  `/api/events` right after the SQL read, so grid, hero, radar, waste and the
  v1 highlights all see the filtered list. The cache keeps everything.
- `closes` is a built-in `school` keyword; `closed` was already a built-in
  `holiday` keyword, so nothing was needed there.
- Tests: `tests/test_importer.py` (rules; writer and both endpoints against
  an in-memory fake calendar), `tests/test_exclusions.py`, plus a family-tag
  test in `test_persons.py`. 54 pass.

**Verified (2026-10-18, dev server on :8001, real calendar).** The daycare
sample from the prompt doc with person *prapti* validated as 6 rows with no
errors and 3 flagged past. Committing the Nov 25 `early_close` and Nov 26
`closed` rows gave `created: 2`. Re-committing gave `exists: 2`, the
November wall-event count stayed at 2, and a re-validate flagged both
`exists`. After the commit's `gcal.run`, `/v2` showed Prapti's NEXT UP as
"Closes 12:00 – Family Luncheon" (Wed Nov 25, 12 PM) and her NEXT HOLIDAY as
"Thu, Nov 26 · Daycare closed – Thanksgiving Day" in red. The 16 excluded
school events are still in the cache but are missing from `/api/events` and
`/v2`; Prisha's NEXT UP skipped the Oct 22 bond forum and the Oct 29 / Nov 2
board meetings to Nov 3 (Uncapped Workday). `writer.delete` removed both
rows (`True`), refused the hand-made "Family Wall Service Account Test"
event, and after refresh *calendars* the family feed had 1 event and
Prapti's column was empty again. The phone layout was checked at 390 px:
single column, no sideways scroll.

Deviations:
- **Id prefix is `fam`, not `wall`.** Google event ids must be base32hex
  (`0-9a-v`), and `w` is outside it: every `wall…` insert came back
  `400 Invalid resource id value`. Ids are `fam` + `sha1(person|date|
  title.lower().strip())[:28]` (31 chars). The *tag* is still
  `source=wall`.
- **New `EVENT_CACHE_DAYS` (default 90).** The fetchers cached only today +
  30 d (`EVENT_HORIZON_DAYS`), so a closure 39 days out never reached the
  hero (the Phase 7 step 2 known limit). The calendar fetchers now cache
  `EVENT_CACHE_DAYS` ahead, and hero/radar/waste read that far.
  `EVENT_HORIZON_DAYS` (30) is still the default `/api/events?days` list, so
  the grid and the v1 agenda are unchanged.
- **Title conventions apply at validate time, not only on commit.** The
  review table shows the title that will be written, and the id (and the
  `exists` check) is computed from it. Commit re-applies them idempotently,
  in case a title was edited. The daycare persons are configurable as
  `IMPORT_DAYCARE_PERSONS` (default `prapti`) instead of hard-coded.
- **Re-importing a deleted event restores it.** Google keeps a deleted
  event's id, so a later insert with that id returns 409. On a 409 the writer
  reads the event: if it is `cancelled`, it is updated back to `confirmed`
  and reported as `created (restored)`; otherwise it is `exists`.
- **Person `family`:** stored as the tag `family`. `persons_for` treats that
  tag as "nobody in particular", so the event lands on the family line even
  when a child's name is in the title.
- Only `kind`, `title` and `date` are required. The other schema keys may be
  missing and are read as null, because models drop null keys.
- `gcal_writer.py` is ~190 lines, not ~120 (it holds the 409 restore path
  and `list_wall`).
- Not built: a same-day reschedule (same person/date/title, new time) shares
  the old id. It shows a warning to change the time in Google Calendar.

---

## Phase 5 — Manageability & deployment polish  [~]

**Goal:** The reason we moved off the old service: easy to manage long-term.

**Remaining in this phase** (deployment is live; these are the open items):
- [x] **Dashboard stale-dot** — done (Pass 5). The staleness math moved from
  `admin.py` into `app/staleness.py` (shared) and a subtle amber corner dot on
  the wall lights when any *active* feed is stale.
- [ ] **Feed editing + "Save & restart" from `/admin`** — write feeds/tunables
  back to `.env` and apply via a service restart (just `nssm restart
  FamilyDashboard`, already documented). Editable settings write to `.env`, never
  a second store (see the Pass 1 env-vs-DB decision below). Only piece of the
  admin page that mutates config; everything read-only shipped in Pass 1.

Done in this phase so far: Pass 1 (admin status + manual refresh), Pass 2 (NSSM
service), Pass 3 (admin logs + source URLs + orphan cleanup), Pass 4 (Pi kiosk).

**Pass 1 done (read-only status + manual refresh)** — verified 2026-08-03 in a
live server + browser. Decided up front: the admin page edits `.env` and applies
via a service restart, *not* a second DB config store — every setting is imported
by value at process start (`from app.config import X` across 11 modules), so
"env vs DB" is really "restart-to-apply vs a whole-app live-reconfig rewrite";
for a one-household wall changed rarely, and with serve-stale making a restart
invisible on the wall, restart-to-apply wins. Only the config-writing feature
pays that cost — the status board, manual refresh, errors and stale-dot need no
config store at all, so they shipped first.
- `app/api/admin.py`: `GET /api/admin/status` (every `fetch_meta` job with a
  computed staleness — 2× interval, or a fixed 26 h window for the nightly cron
  calendars; configured-but-never-fetched feeds still get a row) and
  `POST /api/admin/refresh/{weather|alerts|calendars|photos}` (fires the
  fetcher's `run()` on a daemon thread, returns immediately, never blocks or
  crashes the request). Refresh targets the 4 coarse `run()`s; the status board
  reads the finer `fetch_meta` rows (weather splits into current/forecast/astro,
  calendars into one row per feed).
- `static/admin.html` + `css/admin.css` + `js/admin.js`, served at `/admin`
  (explicit route in `main.py` since the extension-less path isn't a static
  file). Plain table, per-fetcher refresh buttons, polls status every 5 s.
- No changes to `config.py`, the scheduler, or any fetcher — purely additive.

**Pass 2 done (NSSM deployment)** — the Windows-service half of the deploy spec.
- `scripts/install-service.ps1` — idempotent installer (re-run to apply
  changes): wraps `.venv\Scripts\python.exe -m uvicorn app.main:app` (no
  `--reload`, single process so APScheduler isn't doubled) as an auto-start
  service. Sets **`AppDirectory` = repo root** — the load-bearing detail, since
  `load_dotenv()` reads `.env` from cwd, so a wrong working dir silently boots on
  defaults. Restart-on-crash (2 s delay, 5 s throttle), stdout/stderr to
  `data\logs\` with daily+10 MB rotation, and an inbound firewall rule for the
  port. Requires an elevated shell and `nssm.exe` (PATH / `scripts\nssm.exe` /
  `-Nssm`).
- `scripts/uninstall-service.ps1` — stop + remove service and firewall rule;
  leaves code/venv/.env/logs/cache intact.
- `docs/deployment.md` — prerequisites, install, per-setting rationale, verify,
  operations (logs/restart/update/port), uninstall, the manual NSSM equivalents,
  and troubleshooting. README's Deployment section now points here.
- Note for the future admin "Save & restart": it is just `nssm restart
  FamilyDashboard`, documented in the ops section.

**Pass 3 done (admin logs + source URLs + orphan cleanup)** — verified
2026-08-03 in a live server + browser.
- **App-owned rotating log.** New `app/logging_setup.py` attaches a console +
  `TimedRotatingFileHandler` (roll at *local* midnight, `backupCount =
  LOG_RETENTION_DAYS`) to the root logger, writing `data/logs/dashboard.log`.
  Captured however the app is launched (dev or service) and distinct from NSSM's
  stdout capture. `main.py` now calls `configure_logging()` in place of
  `basicConfig`. Config: `LOG_DIR` / `LOG_LEVEL` / `LOG_RETENTION_DAYS` (`.env`).
  Only the app's own `dashboard.*` (+ propagating `httpx`/`apscheduler`) lines
  land here; uvicorn access logs don't propagate, so the 5 s admin poll doesn't
  flood it.
- **Log endpoints:** `GET /api/admin/logs?lines=N` (tail of today's file),
  `GET /api/admin/logs/files` (current + rotated, size/mtime, newest first),
  `GET /api/admin/logs/download?name=` (attachment; whitelisted to real log
  files — `is_log_file` + resolved-parent check refuses `../` traversal and
  non-log files like the DB).
- **Source URLs on the status board.** Each job now carries the URL/point it
  pulls from (feed ICS URL, NWS points/alerts, Open-Meteo, the photos album).
  These are capability URLs; showing them fits the LAN-only model (noted in
  code + the admin page is not for off-LAN exposure).
- **Orphan cleanup.** A `fetch_meta` row with no configured source (e.g. the
  leftover `events:bday` from earlier testing) is flagged `orphaned` and gets a
  "✕ clear" button → `DELETE /api/admin/jobs/{job}` (refuses active jobs with
  409; also drops a removed feed's leftover `events` rows). The stale
  `events:bday` row was cleared.
- Frontend: `admin.html/js/css` gained a Source column, the orphan tag + remove
  button, and a Logs panel (auto-scrolling tail + downloads list).
- `deployment.md` now documents the two log streams; `.env.example` gained the
  Logging section.

**Pass 4 done (Pi kiosk)** — verified 2026-08-03: the wall Pi now shows the
dashboard live. Re-flashed the DAKBoard Pi (Pi 3 B+) with a clean **Raspberry Pi
OS Trixie** (desktop, **labwc/Wayland** session) via Raspberry Pi Imager with a
preset user/password + SSH + WiFi (known credentials, headless). Kiosk is
`~/.config/labwc/autostart` — a self-relaunching Chromium `--kiosk
--ozone-platform=wayland --password-store=basic` loop at `http://192.168.0.68:8000/`
— plus desktop autologin and blanking-off via `raspi-config nonint`. Documented
as `docs/deployment.md` section 7, including the SSH-paste gotchas (indented
heredoc terminators, long lines split mid-paste) and the base64-blob workaround.

**Pass 5 done (dashboard stale-dot)** — verified 2026-08-03 in a live server +
browser. The staleness math (`interval_for`, `stale_after`, `age_seconds`,
`feeds_by_job`, `active_jobs`) moved out of `app/api/admin.py` into a shared
`app/staleness.py` (which also brought admin.py back under the ~200-line rule);
admin now imports it, so the board and the dot can't disagree on "stale."
- `app/staleness.py` adds `summary()` → `{stale, stale_jobs, checked}` over only
  *active* jobs (an orphaned removed-feed row can't light the wall; a
  never-succeeded active job counts as stale). `GET /api/staleness` (new
  `app/api/status.py` router) serves it.
- Frontend: `#stale-dot` in `index.html`, `static/js/staleness.js`
  (`startStaleness`, wired in `main.js`) polls `/api/staleness` on
  `data_refresh_seconds` and toggles a small, dim, slowly-pulsing amber dot in
  the bottom-right — `position:fixed`, `pointer-events:none`, so zero layout
  impact; `prefers-reduced-motion` drops the pulse. Any fetch error just hides
  the dot (the wall never nags). Verified: with the dev cache hours old the dot
  showed and its tooltip listed exactly the stale jobs, while the two calendar
  feeds (inside their 26 h window) were correctly not flagged.

**Still to build:** feed add/remove + `.env` write + the "Save & restart" button
(the only remaining Phase 5 item). (Deployment — Windows service + Pi kiosk — and
the stale-dot are done.)

**Already in place** (reuse, don't rebuild):
- Adding/removing a feed already works without code: set `CAL_<KEY>_URL` in
  `.env` and restart (see Phase 2). The admin page is the *UI* over this —
  it should edit the same `.env`, not a second store.
- `fetch_meta` already records last attempt/success/error per job — the feed
  status list and the stale-dot both read it; no new tracking needed.

**Build:**
- `/admin` page (LAN-only): list feeds with last-fetch time and status,
  add/remove ICS URLs, trigger a manual refresh per fetcher, view recent
  fetch errors. Plain HTML forms, no auth.
- Stale-data indicator on the dashboard (subtle dot when any feed is
  > 2× its refresh interval old).
- NSSM deployment: document install commands, log file redirection to
  `data/logs/`, auto-restart on failure, start-at-boot.
- Pi kiosk checklist (one-time): Raspberry Pi OS, SSH enabled, auto-login,
  Chromium `--kiosk http://<server-ip>:8000/`, cursor hidden, screen
  blanking disabled, optional cron display on/off schedule.

**Done when:** Adding a new ICS feed requires only the admin page (editing
`.env` already suffices today), and the whole system survives a server reboot
with no manual steps.

---

## Phase 6 — Animated ambient background (time × weather × season)  [x]

**Goal:** Replace the flat page background with a living illustrated scene —
trees, shrubs, a small house, and a mountain on the horizon — that continuously
reflects the **time of day**, the **current weather**, and the **season**. It
should feel like a window onto the outdoors, calm enough to sit behind the
dashboard 24/7 without distracting from the panels.

**Current state (keep as the baseline):** the background is `--bg: #08090c` (a
near-black with a faint cool-blue tint; panels are `--panel: #101319`, accent
`--accent: #6fb1ff`). The household *likes* this dark palette — it is the target
look for the **Night** phase, and every other phase should feel like a natural
departure from it, never a jarring bright wash behind the text.

**Inputs — all already available, keep the Pi dumb.** The scene is rendered
client-side (a rendering decision, allowed), but every *input* comes from data
the server already serves, so nothing new is fetched from the Pi:
- **Time of day** → derived in the browser from the clock plus **sunrise/sunset**
  (already fetched into `weather_astro` via Open-Meteo and surfaced in the
  weather API/panel). The dawn/dusk/twilight phases are offsets around those two
  times, not fixed clock hours.
- **Weather** → the current condition/icon from `/api/weather` (the frontend
  already polls it via `startWeather`). `nws_icons.py` tokens
  (clear/partly/cloudy/rain/thunder/snow/sleet/fog/wind/hot) map onto the scene's
  weather animations.
- **Season** → from the current date (northern hemisphere, Harrisburg NC).

**The three dimensions.**

Time-of-day phases (10), boundaries anchored to sun times, not fixed hours:
`Twilight Dawn → Dawn → Sunrise → Morning → Noon → Afternoon → Sunset → Dusk →
Twilight Dusk → Night`. Each sets the **sky gradient**, the **light/“golden
hour” tint** on the scene, and the **celestial body** (sun position/height by
day, moon + stars by night).

Weather states (8), each an **animated** overlay on top of the current phase:
`Clear · Cloudy · Sunny · Rainy · Windy · Thunderstorm · Lightning · Snow`.
(Resolve overlaps when building: *Sunny* vs *Clear* — Clear-by-day reads as
Sunny, Clear-by-night as starfield; *Lightning* is the flash effect that
*Thunderstorm* also uses. Map these from the NWS tokens.)

Seasons (4), setting the **foliage/palette** of the fixed scene features:
`Spring · Summer · Autumn · Winter` (e.g. blossom vs full green vs orange-fall
vs bare/snow-dusted).

**Scene features (constant across all combinations):** a mountain on the
horizon, a small house, trees, shrubs, and a ground plane — each re-skinned by
season and re-lit by phase, with weather animating over the whole.

**Worked example — “Autumn sunset with lightning” (use as an acceptance case):**
- *Season = Autumn*: orange leaves on some branches, fallen leaves on the ground
  and the house roof; occasional wind nudges a few leaves across the scene.
- *Phase = Sunset*: golden-hour palette, the sun low and setting on the horizon.
- *Weather = Lightning*: occasional lightning flashes in the background sky.

**Design constraints (important — this runs forever on modest hardware):**
- **Composed from layers, not 320 hand-drawn scenes.** 10 phases × 8 weather × 4
  seasons is 320 combinations — build them as independent, combinable layers
  (sky gradient by phase; celestial by phase; scene silhouette fixed; foliage
  palette by season; weather animation overlay) so any combination just stacks.
- **Cheap enough for the wall Pi (Raspberry Pi 3 B+, Chromium/labwc Wayland),
  running 24/7.** Prefer SVG + CSS animations/transforms (GPU-friendly) over a
  heavy per-frame `<canvas>` loop; cap particle counts; pause/relax animation at
  Night. It must not peg the CPU or heat-throttle the Pi.
- **Legibility first.** The dashboard panels and text must stay perfectly
  readable over the scene — keep panels on their solid `--panel` fill and/or add
  scrims; the scene is ambience, never foreground.
- **No external assets.** Draw everything locally (like the weather glyphs in
  `index.html`) — the page must never fetch images/CSS/JS from outside this
  server.
- Honour `prefers-reduced-motion` (drop or slow animations), and it must survive
  the nightly 03:00 reload without leaking timers/memory.

**Open decisions to settle at the start of the build:**
1. **Where the scene lives.** Full-bleed behind the whole grid (panels stay
   opaque, so the scene shows in gaps/around panels), or specifically as the
   backdrop of the **photo column** (and how it coexists with / toggles against
   the existing photo slideshow). This choice drives everything else.
2. **Render tech:** layered inline SVG + CSS keyframes (leaning this way for Pi
   perf) vs a light canvas. 
3. **Phase-boundary math:** exact offsets that define Dawn/Dusk/Twilight around
   sunrise/sunset.
4. **Weather-token → animation mapping**, including the Sunny/Clear and
   Lightning/Thunderstorm overlaps above.

**Build (suggested decomposition):**
- A `background.js` module + `background.css` (+ inline SVG defs), started from
  `main.js` with the same `settings`, that reads clock + sun times + weather +
  date and sets phase/weather/season classes on a scene container.
- Layer 1 sky (phase gradient) → Layer 2 celestial (sun/moon/stars) → Layer 3
  parallax scene silhouette (mountain/house/trees/shrubs/ground, season-skinned)
  → Layer 4 weather animation (rain/snow/clouds/wind/lightning).
- Build one vertical slice first (e.g. the worked example) to prove the layer
  stack, then fill in phases/weather/seasons.

**Done when:** the wall background visibly tracks real sunrise/sunset through the
day, changes with the live weather, and shows the right seasonal foliage — with
the dashboard panels still fully legible and the Pi staying cool, over a full
day of unattended running.

**Verified 2026-08-03** at a forced 1920×1080 layout box, against the live
weather feed and by forcing representative combinations. Live boot resolved to
`phase-sunset / weather-thunder / season-summer` off the real clock + the served
sun times (sunrise 06:33, sunset 20:24) and the current NWS icon token, with the
sun placed low on the setting arc (`--sun-x 98%`, `--sun-y 9.4%`) and the moon
parked. `#scene` sits at `z-index: 0`, `.dashboard` at `z-index: 1`; no scroll on
either axis (1920×1080 exact); console clean apart from the pre-existing favicon
404. Panels stayed fully opaque and legible across a **bright summer noon** (the
brightest phase) — a calm blue frame, not a wash. Peeking behind the panels
confirmed the full layer stack composes per combination: the **acceptance case
"autumn sunset + lightning"** (orange canopies, fallen leaves, mountains, rain
streaks under the thunder overlay, warm sunset gradient), a **summer noon**
(sun high with its glow, blue sky, green foliage), and a **winter night**
(starfield, glowing moon on its night arc, snow-capped mountains, snow-dusted
canopies + ground, falling snow, and the house window warmly lit — the night-only
glow firing correctly).

**Deviations from spec** (all additive unless noted):
- **Scene placement: full-bleed, "gaps only" (household choice).** Of the two
  open options, the household picked the scene living behind the whole grid with
  the panels **fully opaque** — so it shows in the padding frame and the gaps
  between cells, never behind the text. No panel translucency, no photo-column
  takeover; the photo slideshow is untouched. `#scene` is a fixed layer at
  `z-index: 0`; `.dashboard` got `position: relative; z-index: 1` to sit above
  it. This is the most legibility-safe reading of the spec's option 1.
- **Render tech: layered inline SVG + CSS keyframes, no canvas** (settling open
  decision 2 the Pi-friendly way). Everything animates via GPU-friendly
  `transform`/`opacity` only. Weather particles are a **couple of tiled
  background-image sheets translated with `transform`** (rain = diagonal
  `repeating-linear-gradient` streaks; snow = radial dot pattern with lateral
  drift), not per-drop DOM nodes — one compositor layer each, so particle count
  is fixed regardless of "density." Stars are a static two-layer radial-gradient
  dot field (no nodes). Clouds are three soft blobs. This keeps it cheap enough
  for the Pi 3 B+ running 24/7; not yet measured on the Pi itself over a full day
  (the spec's "stays cool" clause) — flag for a wall check.
- **Phase-boundary math (open decision 3).** Ten phases anchored to the served
  sunrise (SR) / sunset (SS) as minute offsets, evaluated in clock order:
  night `< SR−90 or ≥ SS+90`, twilight-dawn `SR−90`, dawn `SR−40`, sunrise
  `SR−10`, morning `SR+25`, noon `midpoint±75`, afternoon, sunset `SS−25`, dusk
  `SS+10`, twilight-dusk `SS+40 … SS+90`. Sun/moon ride a `sin` arc between their
  times; JS writes only `--sun-x/y`, `--moon-x/y` once a minute and the layer
  visibility is pure CSS off the phase class.
- **Weather-token → animation mapping (open decision 4).** NWS/`nws_icons.py`
  tokens map to eight states: `clear`/`clear-night`→clear (sun or starfield does
  the work), `hot`→sunny, `partly`→light cloud, `cloudy`→overcast, `rain`→rain,
  `thunder`→thunderstorm **with the lightning flash** (Lightning is the flash
  effect, not a separate token), `snow`/`sleet`→snow, `fog`→fog band, `wind`→
  windy (speeds up cloud drift + tree sway). Clear-by-day therefore reads as
  Sunny and clear-by-night as the starfield, per the spec's overlap notes.
- **Small server addition:** `/api/weather`'s `current` now also carries raw local
  ISO `sunrise_at` / `sunset_at` (the panel's formatted `sunset` is unchanged).
  The times were already fetched into `weather_astro` (Open-Meteo) but only the
  formatted sunset was surfaced; the background needs the machine-readable pair
  for the phase math. Still no new Pi fetch — `background.js` reads the same
  cached `/api/weather` the weather panel already polls.
- **New files:** `static/js/background.js` (the driver — reads clock + sun times +
  condition + date, sets phase/weather/season classes and celestial vars) and
  `static/css/background.css` (all four layers + keyframes). Scene markup + the
  fixed landscape SVG (mountain, house w/ night-glow window, 3 trees, 3 shrubs,
  ground, seasonal snow/blossom/fallen-leaf extras) is inline in `index.html`
  like the weather glyphs. `main.js` wires `startBackground(settings)` on the
  same settings object; nothing else changed.
- **`prefers-reduced-motion`** drops every animation but keeps the still picture
  (gradient, sun/moon position, foliage). The nightly 03:00 reload resets the two
  `setInterval`s (minute tick + weather poll), so no timer/memory leak across
  days.
- **Foliage/season is by calendar month** (Dec–Feb winter, Mar–May spring, etc.),
  not the astronomical equinox/solstice — simpler and indistinguishable on the
  wall. Winter also snow-dusts the canopies/roof/ground and caps the mountains;
  spring adds blossoms; autumn adds fallen leaves + orange canopies.
- **Frosted-glass panels (later refinement, household ask).** Every panel —
  calendar, agenda, ticker, weather **and the photo column** — went from a solid
  fill to a semi-transparent tint (`--panel-glass`, `rgba(16,19,25,0.28)`) plus
  `backdrop-filter: blur(--panel-blur=13px)`, so the ambient scene shows through
  as a soft dimmed wash and the background "comes alive" instead of only peeking
  through the gaps. The inner tiles (calendar day cells, weather forecast cards)
  use a near-transparent `--box-glass` + hairline `--box-edge` so they read as
  frosted tiles rather than solid blocks; the photo column's per-photo blurred
  fill was made translucent so the scene shows in the letterbox areas too.
  Verified legible even at the brightest phase (summer noon) and through a warm
  sunset. **Caveat:** `backdrop-filter` over the animated scene is continuous GPU
  work — untested on the wall Pi (Pi 3 B+); it is a single CSS var (set
  `--panel-blur: 0` to drop it), and an `@supports not (backdrop-filter)` fallback
  returns panels to near-opaque. Watch CPU/temp on the wall; dial back if it
  throttles.
- **Optional raster backdrop (built).** `docs/background-prompts.md` has 40
  copy-paste image-gen prompts (season × phase) to pre-render the scene as art;
  the recommendation is those 40 stills + the existing CSS weather overlay, not
  320 animated loops (which would heat-throttle the Pi). `background.js` now
  swaps a `/img/bg/<season>-<phase>.jpg` in as a crossfading backdrop layer
  (`.scene-photo`, two layers) **above the SVG scene but below the weather
  overlays**, so rain/snow/clouds/lightning still animate on top of the image.
  A new `GET /api/backgrounds` (`app/api/backgrounds.py`) lists which images
  exist under `static/img/bg`; the frontend reads it once and only requests a
  present image, so not-yet-generated combos **fall back to the live SVG with no
  404**. Occluded SVG animations (stars, tree-sway) pause under an active photo.
  Verified end-to-end against a real generated night image at the live combo:
  manifest hit → single request → crossfade in → `has-photo`, cloud overlay
  compositing over it, panels legible, console clean (bar the favicon 404).
  Images are a drop-in — the SVG scene renders wherever an image is absent. The
  full 40-image set (season × phase) was generated and is committed; a one-off
  `scripts/compress_backgrounds.py` (Pillow, dev-only, in `requirements.txt`
  under a tooling section) shrank them ~93% (74 MB → 5.3 MB) before commit.
- **Weather-overlay polish (household feedback).** The overlays were tuned on the
  wall: snow denser with bigger flakes; wind given a sliding streak overlay plus
  wider tree-sway and faster clouds; lightning brightened to a double-strike;
  thunderstorm darkened with a moody vignette so it reads distinct from plain
  rain even between flashes. Rain was reworked twice — from continuous
  `repeating-linear-gradient` lines (read as static hatching / fast-moving
  streaks) to **short tiled drops** (elongated radial-gradient dots falling
  exactly one tile per loop, so it's seamless and reads as gentle rain, not
  sliding lines). All still pure transform/opacity on fixed-count layers.

---

## Phase 7 — Light layout v2 (per-person wall)  [x]

**Goal:** A new default page that shows the same data as the current wall in
the household's new design: light cyan canvas, Oswald clock, DM Serif titles, a
gold "next up" hero split per child, a family line, a colour-coded waste strip,
a Sunday-first month grid with a 30-day "on the radar" footer, and the photo
slideshow in a full-height right column. Static mockup with dummy data (the
spec for this phase): `docs/mockups/family_dashboard_v2_mockup.html`.

**Routing (done, step 4):** the new page is `/`; the current wall moved to `/v1` (its
assets stay at `/css`, `/js`; the new page uses `static/v2.html` + `css/v2/` +
`js/v2/`). `/v2` stays as an alias of `/`. The Pi kiosk URL is unchanged, so
**the wall flips after the deploy restart** (on its next reload, see Deviations)
— accepted by the household.

**Reuse, don't rebuild:** `clock.js`, `reload.js`, `dates.js`, `photos.js`
(slideshow), `/api/settings`, `/api/photos`, `/api/weather`, `/api/events` and
every fetcher. New renderers only where the DOM differs (`calendar.js` and
`weather.js` are bound to the v1 ids).

**Decisions (2026-10-18):**
- **Persons.** A person is a set of feeds plus a name match, declared in `.env`:
  `PERSON_<KEY>_LABEL/_COLOR/_ORDER`, `PERSON_<KEY>_FEEDS` (feeds wholly
  theirs — `school` for Prisha now, for both next year) and
  `PERSON_<KEY>_KEYWORDS` (word-boundary title match, e.g. `prisha`). Events
  from the Google feed carry a `person` tag (Phase 4) which wins; the keyword
  match is the fallback for hand-entered events. An event matching nobody from
  the family feed is *Family*. Served as `persons` + per-event `person` on
  `/api/events`, computed server-side (Pi stays dumb).
- **Grid colour** is by feed for school/trash, and by person (else family) for
  family-calendar events. Legend: Prisha · Prapti · Family · School · Trash.
  Category tints (holiday/dismissal/quarter) unchanged.
- **Hero** = two person columns (first two persons by `_ORDER`), each: NEXT UP
  (earliest upcoming event across their feeds + matches) and, in the former
  "THEN" slot, **NEXT HOLIDAY** — earliest `holiday`-category event in the same
  set, larger type ("Wed, Nov 11 · Veterans Day"). Different per child because
  the daycare and the school close on different days.
- **Family line** — one row under the kids, above the waste strip: the next
  family event, then the following one, ellipsised.
- **Waste strip** — text: the next pickup and its items (from the trash feed,
  `TRASH_REMINDER_KEYWORDS`). Colour follows the **next un-passed pickup inside
  the current Sun–Sat week**: contains *recycling* → green, else contains
  *bulky* → orange, else blue — recycling > bulky when a pickup lists both
  (they share a day in this feed); once the week's pickups have passed it
  rolls to next week's first. `WASTE_SPECIAL_RECYCLE/BULKY_KEYWORDS` + colours in `.env`.
- **On the radar** footer — `HIGHLIGHT_KEYWORDS` minus the trash terms
  (`first day of school, early dismissal, no school, holiday, end of quarter,
  capped workday`), window **30 days** (`RADAR_DAYS`), "Nov 26–27 Thanksgiving
  Break" style with multi-day spans collapsed. The v1 ticker's 7-day
  `highlights` stays for `/v1`.
- **Weather** — °F with °C in brackets as today; **six hourly slots** from the
  next hour (new) and the **next 3 days** from the existing daily rows.
  `fetchers/weather.py` gains the NWS `/forecast/hourly` call on the same
  gridpoint inside the `weather:forecast` job, a `weather_hourly` table, and
  `/api/weather` gains `hourly[]`.
- **Month grid** Sunday-first, 5 or 6 rows as the month needs (not the mockup's
  fixed 5), chip-fit measured as in v1.
- **Dropped on this page** (household: "it was not working anyway"): alerts
  pill, highlights ticker, stale-dot, ambient background, agenda list. All stay
  on `/v1`; nothing is deleted.
- **Fonts vendored**: Oswald, DM Serif Display, DM Sans as `.woff2` under
  `static/fonts/` — the page must not fetch from Google Fonts (Pi may be
  offline; page-never-calls-external rule).
- The mockup's CSS (seven stacked override blocks) is **not** copied; the
  computed result is reproduced in one clean stylesheet.

**Build order:** (1) hourly fetcher + `/api/weather.hourly`; (2) persons in
`config.py` + `/api/events` (`persons`, `person`, `radar`, `waste`); (3)
`static/v2.html` + CSS + renderers, verified at a forced 1920×1080 box against
live data; (4) route swap `/` ↔ `/v1`; (5) PLAN/README/deployment notes.
Phase 4's Google feed is not a prerequisite — until it lands the family column
and Prapti's column simply have less to show.

**Done when:** `/` renders the mockup's layout with live data at 1920×1080 with
no scroll, both children's columns and the family line fill from real events,
the waste strip changes colour on a recycling week, and `/v1` still works.

**Step 1 done (2026-10-18) — hourly forecast.** `nws.resolve_grid()` now also
returns `forecastHourly`; the fetch + parse live in a new helper
`app/fetchers/weather_hourly.py` (no `run()` of its own — keeps `weather.py`
under ~200 lines), called from `weather.run()` after the daily forecast and
current conditions, and recorded as `weather:hourly`. Table `weather_hourly`
(start_utc PK, UTC ISO) holds current hour + 23, replaced wholesale. `/api/weather` gains `hourly[]`
(6 slots, `label/temp_f/temp_c/icon/condition/precip_pct`); `weather:hourly`
is in `staleness.active_jobs` and the admin source map. Verified live: 24 rows,
6 slots starting at the next local hour; an unroutable hourly URL left
daily/current fresh and kept the last-good hourly rows, with the error on `weather:hourly` only.
Deviations:
- `temp_c` is computed server-side; v1's current block actually converts in
  the browser (`static/js/weather.js` `toCelsius`), same rounding.
- `last_updated` on `/api/weather` still tracks current + forecast only
  (envelope unchanged); hourly staleness shows via `/admin` and the stale-dot.
- The table keeps the hour in progress as slack; `/api/weather` serves slots
  strictly after it (the next local hour onward), as the Weather decision says.
- Hourly is fetched last in the weather job, so an unreachable hourly host
  (one `FETCH_TIMEOUT_SECONDS`) never delays current conditions.

**Step 2 done (2026-10-18) — persons, hero, radar, waste on `/api/events`.**
`config.py` discovers `PERSON_<KEY>_LABEL/_COLOR/_ORDER/_FEEDS/_KEYWORDS` into
`PERSONS` (dataclass `Person`, palette fallback like feeds) and adds
`PERSON_COLOR_FEEDS`, `FAMILY_FEEDS`, `HERO_HOLIDAY_CATEGORIES`,
`RADAR_KEYWORDS/_DAYS`, `WASTE_RECYCLE/BULKY_KEYWORDS`; `.env` seeds Prisha
(feeds=school, order 1) and Prapti (keywords only, order 2). `events` gains
nullable `person` and `kind` columns; `init_db` adds missing ones via
`PRAGMA table_info` + `ALTER TABLE` (nothing writes them yet; Phase 4 will).
Attribution (`persons_for`, `display_color`) is in `app/persons.py`; the hero /
radar / waste blocks are pure functions in `app/events_derived.py` over the
API's own event dicts. `/api/events` gains top-level `persons`, `hero`,
`radar`, `waste`, and per event `persons` + `color`; every v1 key was verified
identical to the pre-change endpoint (default and `?days=7`) and `/v1`'s page
renders as before. 26 pytest tests in `tests/` (`python -m pytest`, config in
`pytest.ini`). Live: Prisha's NEXT UP / NEXT HOLIDAY fill from the school feed;
Prapti and family are null until Phase 4, as expected.
Deviations:
- Per-event attribution is `persons: [keys]` (a list), not the single
  `person` the Persons decision names — a school event belongs to everyone
  whose FEEDS lists `school`.
- **Bulky and recycling do share a day** in the Concord ReCollect feed (every
  other Wednesday: "Yard Waste · Bulky Waste · Recycling · Garbage"). The
  household rule is recycling > bulky, so that pickup is "recycle" (green) and
  "bulky" only shows for a bulky-only pickup.
- `week_kind` is simply the first pickup from today on: "first un-passed
  pickup in this Sun–Sat week, else the first after it" is always that one.
  Same-day pickup events are merged into one entry (items deduped).
- Radar keywords match as a case-insensitive substring (like the v1
  highlights); person keywords are word-boundary (`event_styles` regex, now
  exposed as `compile_keywords`). `alert_rules._matches_trash` is now public
  `matches_trash`, reused for waste.
- hero/radar/waste read everything cached ahead
  (`max(days, EVENT_HORIZON_DAYS, RADAR_DAYS)`) regardless of `?days`; the
  `events` list is still cut at `days`. NEXT HOLIDAY can only see as far as
  the cache (30 days) — it is null when no holiday falls in that horizon.
- `config.py` grew to ~430 lines; split right after (see below).

**Step 2 follow-ups (2026-10-18).** Waste is recycling > bulky; `app/config.py`
is now the package `app/config/` (`env`, `feeds`, `persons`, `weather`,
`alerts`, `display`; photo settings went to `display`), with `__init__`
re-exporting all 55 public names, values verified identical.

**Hero refinements (2026-10-18).** NEXT UP now skips `HERO_HOLIDAY_CATEGORIES`
events (they are already on the NEXT HOLIDAY line); holidays still feed
next_holiday, the grid and the radar. New optional `CAL_<KEY>_CLOSED_LABEL`
(`CalendarFeed.closed_label`; `.env` sets `CAL_SCHOOL_CLOSED_LABEL=School closed`):
holiday events from that feed show "<label> – <title before its first ':'>" on
the hero next_holiday and radar entries (a copy; grid chips and the raw title
are unchanged). Radar keyword matching/dedupe still use the raw title. Live:
Prisha next_holiday "School closed – Uncapped Workday/Election Day", next Dec
18; Prapti next Nov 25 early close, next_holiday Nov 11.
The twin `CAL_<KEY>_DISMISSAL_LABEL` (`.env`: `CAL_SCHOOL_DISMISSAL_LABEL=Early
dismissal`) labels early-dismissal events on NEXT UP / NEXT HOLIDAY and the radar;
both rules live in `app/event_labels.py` (`labelled`, `TitleLabels`). Deviations:
the dismissal rule fires when the title *matches* the `school` category, not only
when it wins — "End of Quarter/Early Dismissal" is drawn as `quarter` (order 10).
Cleaning drops the whole "/"- or " - "-separated part naming the label, not just
the label words, since the live title has no colon ("…/Early Dismissal for
traditional calendar students"). Live: Prisha NEXT UP Dec 18 "Early dismissal –
End of Quarter".

**Separate dismissal category (2026-10-18).** The built-in `school` category is
split: `dismissal` (early dismissal, early release, closes, half day; order 5)
and `school` (first/last day of school; order 20), both gold `#ffab00`.
`EVENT_STYLE_DISMISSAL_*` works like the other categories; `.env` also sets
`EVENT_STYLE_DISMISSAL_COLOR`. The dismissal label now keys on `category ==
"dismissal"` exactly as the closed label keys on holiday, so the keyword-match
special case above is gone. Order 5 puts `dismissal` ahead of `quarter` (10),
so **Dec 18 "End of Quarter/Early Dismissal…" now tints gold, not purple**.
(Oct 9 "End of *First* Quarter/ Early Dismissal…" was already gold: it never
matched "end of quarter".) Deviation: "adjacent order" to school was not
possible while also beating quarter. `CLOSURE_ALERT_CATEGORIES` stays
`school, holiday` in that commit; the follow-up "alerts: include dismissal
category" makes the default (and `.env`) `school, holiday, dismissal`, so early
dismissals (incl. daycare "Closes 12:00") raise the red closure alert again.

**Step 3 done (2026-10-18) — the v2 page at `/v2`.** `static/v2.html` +
`css/v2/` (`base` tokens/fonts/frame, `header`, `hero`, `month`, `photo`) +
`js/v2/` (`main`, `util` poll/el helpers, `format`, `date-line`, `weather`,
`hero`, `month`); `main.py` gains an explicit `GET /v2` before the `/` mount.
Reuses `clock.js`, `photos.js`, `reload.js`, `dates.js` unchanged (v2.html
carries their ids/classes); no v1 file touched. Fonts vendored as three
variable-weight latin woff2 files in `static/fonts/` (Oswald 400–700, DM Sans
400–800, DM Serif Display 400; ~83 KB total), preloaded, with fallback stacks.
Each region polls its API on `data_refresh_seconds`, and a failed poll is
skipped. CLAUDE.md now points at `app/config/`.
Verified at a forced 1920×1080 viewport on port 8001 against the live cache
(screenshot `docs/mockups/v2-live-2026-10-18.png`):
- Box-for-box against the mockup render: 25 of 27 measured regions (header,
  clock, date, weather blocks, hero, kids, person, title, details, holiday
  line, family line, waste strip, calendar, heading, today pill, grid,
  weekday row, cell, chip, footer, photo) match x/y/w/h and font size exactly
  — header 162 px, hero 262 px (kids 186 / family 36 / waste 40), calendar
  605 px, grid 5 weeks × 101 px rows, photo 614×876. Differences are content
  only: `.degrees` starts 14 px further right (46 px SVG glyph vs. the
  mockup's emoji) and the legend is narrower (no Family entry, see below).
- `scrollWidth/Height` = 1920/1080; console has only the favicon 404; the
  resource list contains only `localhost:8001`.
- Empty states (stubbed hero nulls, empty radar/waste) render "Nothing
  scheduled", "No holiday in the next 30 days", "Nothing on the family
  calendar", "No pickups found", "Nothing on the radar". Every region box is
  unchanged except the radar text span, which just gets shorter.
- With all `/api/*` aborted after first render and every poll timer fired,
  the DOM is identical (weather, hero, grid, chips, current photo).
- Stubbed August 2026: `--weeks` 6 (42 cells), 9 events in one cell →
  2 chips + "+7", no overflow, still no scroll; `week_kind` recycle → green
  `#1f9d55` / "RECYCLING WEEK", bulky → orange `#e07a1f` / "BULKY WEEK".
- `/` still serves the v1 wall (`/js/main.js`, grid/agenda/forecast/ticker
  render, no console errors). 27 pytest tests pass.
Deviations:
- The legend is persons + feeds as specified ("Prisha · Prapti · School ·
  Trash"). Family has no entry: it isn't a feed and has no colour in the API
  yet. The family-line dot uses the mockup's `--family` token.
- Chip colours are the server's `event.color`, so school chips are `#74c0fc`
  (the feed colour), not the mockup's slate `#5b7fa3`. Oct 9 tints amber
  because its event is categorised `school` ("End of First Quarter / Early
  Dismissal") — the dominant-category rule, same as v1.
- The today cell keeps its gold styling and is never category-tinted (the
  mockup does not show that case; v1 lets the tint through).
- The waste strip's "▤" glyph is a small inline SVG bin (the Pi's fonts may
  not have the glyph). Empty states keep their labels (NEXT HOLIDAY / FAMILY
  / NEXT COLLECTION) with the wording in the content slot. An empty
  `week_kind` falls back to "regular".
- H/L: after ~6 PM NWS drops today's daily row, so H/L falls back to
  `current.high_f/low_f`. Tonight that is "L 38°" only; missing parts are
  omitted. UV gets a WHO band ("5 Moderate"), computed in the browser.
- The clock's meridiem is uppercased in CSS. clock.js writes it lowercase.
  The date line ("SUNDAY October 18") is a small v2 module because
  clock.js's date format differs and v1 modules stay untouched.
- The mockup's phone fallback media query and photo caption are not carried
  over (wall-only page; no caption per spec).

**Step 3 visual tuning (2026-10-18), CSS only.** Larger type for reading
across the room. Region boxes are unchanged (header 162, hero 262 = 186/36/40,
calendar 605, photo 614×876); longer text is absorbed by the existing ellipsis
and chip fitting. New sizes:
- Header: the current-conditions row is centred in weather-left (242 px each
  side tonight); temperature 42px (was 62px), with the temperature and
  condition block both centred at y=48; FEELS LIKE / HUMIDITY / UV labels
  13px, values 15px (were 10px); hourly labels 13px, temps 15px (were 11/13).
  The H/L line already drops a missing H ("L 38°" tonight), so no JS change.
- Hero: person details 15px, family line 15px (were 13px); holiday "what" 18px
  (was 16px); waste strip 14px (was 12px), its NEXT COLLECTION label 12px
  (was 10px), state label 11px (was 9px).
- Month: chips 12px (was 9px), padding 4px 5px; day numbers 18px (was 16px);
  weekday headers 12px (was 10px); today tag 9px (was 7px); footer, its
  ON THE RADAR label and legend 12px (were 10/9/10px). "+N" stays 9px.
Verified at 1920×1080 on port 8001 (`docs/mockups/v2-live-2026-10-18-tuned.png`):
scroll 1920/1080; 20 chips, none clipped vertically or past its cell, no
"+N" needed for tonight's data; no overflow in the metrics row, footer,
family line or waste strip; console has only the favicon 404.
Side effect: at 14px the waste strip no longer fits both pickups, so the
next pickup's items ("Yard Waste · Garba…") ellipsise along with the "Then …"
part. Pinning the next pickup (`flex: none` on `.waste-type`) would leave
only "Then …" to shrink; not done here (no layout changes in this pass).

**Step 3 header rework + holiday colour (2026-10-18).** The header is four
zones in one 162 px row (`grid-template-columns: .62fr .72fr 1.35fr .95fr`,
gap 28 → 306 / 355 / 666 / 469 px). The bottom rule is the header's own 2 px
border under all four zones (replaces the per-section `.rule` divs).
`.weather-layout`, `.weather-left` and `.weather-right` are gone; every
element id/class the renderers and clock.js write into is unchanged.
- Clock: time 96px, AM/PM 20px; date on one line "SUNDAY · October 18"
  (15px/21px). The zone sits at the bottom, just above the rule.
- Now: vertically centred, left-aligned. Icon 36px + temperature 48px +
  "(13°C)" 16px on a shared baseline; condition 13px/800 + "H · L" 12px
  muted; metrics as one line "FEELS LIKE 55° · HUMIDITY 38% · UV 5
  Moderate" (labels 12px/800 muted, values 14px ink, `::before` dots, no
  borders). The HTML label "UV INDEX" is now "UV".
- Next 6 hours: 10px kicker, six slots in `repeat(6, 1fr)` centred in the
  remaining height (label 13px, icon 22px, temp 15px/800; each slot's
  content stays centred over its column, as before).
- Next 3 days: unchanged, left border kept.
- Holiday line: `.has-holiday` turns label, date and title `--holiday-ink`
  `#b3261e` (new token); label 85% opacity, 7 px red dot before the date.
  The "No holiday…" state keeps the muted gold ink and has no dot.
- Waste strip: `.waste-type` is `flex: none`, so the next pickup stays whole
  and only "Then …" ellipsises.
- JS, two one-line changes the spec needs (the CSS can't make them):
  `hero.js` adds the `has-holiday` class; `weather.js` joins H/L with " · ".
  A missing H is still dropped ("L 38°").
Verified at 1920×1080 on port 8001 (`docs/mockups/v2-live-2026-10-18-header.png`):
scroll 1920/1080; header 162 px, all four zones end at y=176 on the rule.
No element sticks out of its zone and no text is ellipsised, both live and
with a stub at the extremes (102° / 39°C, feels 108°, humidity 100%,
"Partly Cloudy", "5 Moderate", H 104° · L 100°, hourly 101°, daily
"Partly cloudy" 103°/100°, clock "12:59 PM" / "WEDNESDAY · September 30").
Console: only the favicon 404.

**Step 4 done (2026-10-18) — route swap.** `main.py` gains explicit `GET /`
(and `/v2`, same handler) → `static/v2.html` and `GET /v1` →
`static/index.html`, registered before the `/` StaticFiles mount, which stays
last with `html=True` so `/css`, `/js`, `/img`, `/fonts`, `/photos` resolve as
before. No v1 file moved. `requirements.txt` pins the step 2/3 additions to the
installed versions (`pytest==9.1.1`, `google-api-python-client==2.201.0`,
`google-auth==2.62.0`, `tzdata==2026.3`).

**Step 5 done (2026-10-18) — docs.** README (features, layout, configuration,
roadmap), `docs/deployment.md` ("Updating the wall"), this file.
`.env.example` re-checked: every `PERSON_<KEY>_*`, `PERSON_COLOR_FEEDS`,
`FAMILY_FEEDS`, `HERO_HOLIDAY_CATEGORIES`, `RADAR_*` and `WASTE_*` key is listed
with a comment.

**Verified 2026-10-18** on a fresh dev server on port 8001, against the live
cache. `GET /` and `GET /v2` return 200 and are byte-identical to
`static/v2.html` (first stylesheet `/css/v2/base.css`), which shows the explicit
route wins over the mount's `index.html` fallback. `GET /v1` returns
`static/index.html` byte-for-byte (first stylesheet `/css/style.css`). `/admin`
is identical to `static/admin.html`. `/api/events`, `/api/weather`,
`/api/settings`, `/api/photos`, `/api/admin/status`, `/healthz`, `/css/style.css`,
`/js/main.js`, `/css/v2/base.css`, `/js/v2/main.js` and
`/fonts/oswald-latin.woff2` all return 200. In Chromium at 1920×1080, `/` loads
`/js/v2/main.js` with scroll 1920/1080, 20 month chips, Prisha's NEXT UP
(Thu Oct 22, 6:30 PM) and NEXT HOLIDAY (Tue, Nov 3) from live data, waste
`regular`, and only `localhost:8001` in the resource list. Its console was
clean. `/v1` renders the old wall (`/js/main.js`, 5 v1 stylesheets, grid,
forecast, ticker "Oct 21 Yard Waste") with scroll 1920/1080, and its console
showed only the long-standing favicon 404. 27 pytest tests pass.

**Deviations from spec** (summary; the per-step notes above have the detail):
- Hourly: `temp_c` is computed server-side. `/api/weather`'s `last_updated`
  still covers current + forecast only, and hourly staleness shows via `/admin`.
  Hourly is fetched last in the weather job, in a helper module.
- Persons: per-event attribution is a list (`persons: [keys]`), not a single
  `person`. Every event also carries a server-computed `color`.
- Waste: recycling and bulky share a pickup day in the Concord feed, and
  recycling wins. `week_kind` is simply the first pickup from today on. The
  strip colours are CSS tokens (`--strip-recycle` / `--strip-bulky` in
  `css/v2/base.css`), not `.env` keys. The keyword keys are
  `WASTE_RECYCLE_KEYWORDS` / `WASTE_BULKY_KEYWORDS`.
- Radar keywords match as substrings (like v1 highlights). Person keywords
  match on word boundaries. hero/radar/waste read the whole cache regardless of
  `?days`, so NEXT HOLIDAY sees at most 30 days ahead.
- `app/config.py` became the package `app/config/` (its public names are
  unchanged).
- Page: the legend has no Family entry. Chips use the server colour, so school
  chips are `#74c0fc`. The today cell is never tinted. The bin glyph is an
  inline SVG. H/L falls back to `current.high_f/low_f` in the evening. The date
  line is its own small module. There is no phone media query and no photo
  caption. Type was enlarged and the header reworked into four zones, with a
  red NEXT HOLIDAY when one is set.
- Routing: `/v2` is kept as an alias of `/`. Without `Cache-Control`, a
  Chromium that had cached the old `/` (v1's `index.html`, last modified Aug 4)
  treated it as fresh for about a week on a plain navigation. This was seen in
  testing, and a reload showed v2. Fixed in the follow-up below, except for a
  copy the Pi cached before the fix (see `docs/deployment.md`).

**Follow-up (2026-10-18) — no-cache pages, larger hourly slots.**
- `/`, `/v2`, `/v1` and `/admin` now send `Cache-Control: no-cache` and answer
  HEAD as well as GET. Before this, `curl -I /` fell through to the mount and
  reported v1's `index.html`, and HEAD on `/v1`, `/v2` and `/admin` returned
  404. The mounts are unchanged, so assets stay cacheable.
- Next 6 hours: kicker 11px (was 10px; the NEXT 3 DAYS kicker was already
  11px), slot label 17px/700, icon 36px, temperature 22px/800, gap 2px. Every
  size fit as requested, with no icon reduction and no column change.
- Verified at 1920×1080 on port 8001: each slot's content is 91 px tall inside
  a 144 px area under the kicker. With 103° in all six slots, a temperature is
  45 px wide inside a 111 px slot, and nothing sits outside its slot or zone.
  Scroll 1920/1080. The header is 162 px with its 2 px rule at y=176. Console:
  only the favicon 404. 27 tests pass.

**Night mode (2026-10-19) — midnight → sunrise.** Spec:
`docs/mockups/family_dashboard_v2_night_mockup.html` (its `html.night` block).
From `NIGHT_MODE_START` (`app/config/display.py`, default `00:00`, served as
`night_mode_start` on `/api/settings`, in `.env.example`) until the day's
sunrise, `<html>` carries the class `night` and the page uses a dark palette.
Layout and type do not change.
- `static/js/v2/night.js`: `startNight(settings)` re-checks on every minute
  boundary in the display timezone. Sunrise is `current.sunrise_at` from the
  weather renderer's existing `/api/weather` poll: `weather.js` hands it over
  through `setSunrise()`, so there is no second fetch. If the cache is empty or
  `/api/weather` fails, 06:30 is used. Wired from `main.js` like the other starters.
- `static/css/v2/base.css`: an `html.night` token block with the mockup's
  values, plus 25 one-line per-component overrides from the mockup's
  `html.night` rules. The flips fade over 1.5 s
  (`prefers-reduced-motion: no-preference` only).
- Docs: `docs/deployment.md` §7 "Nightly Chromium restart" (Pi user crontab
  `5 3 * * * /usr/bin/pkill -f chromium` + `timedatectl` check; installed on
  the wall Pi 2026-10-19).

Verified at 1920×1080 on port 8001, using the live cache (sunrise 07:32):
- Day palette unchanged. With the class off (clock pinned to noon), a dump of
  2,288 elements is byte-identical to the pre-change code. The dump covers
  colour, background colour and image, border colours, opacity, fill, shadow,
  font size, colour scheme and box.
- Class forced on: screenshot `docs/mockups/v2-night-live-2026-10-19.png`, next
  to the mockup render. Scroll is 1920/1080. Hero `#2a2300` / ink `#f3cf2e`,
  holiday `#c9655a`, regular strip `#0d2a35`, chip 22% mix, photo opacity .72,
  `color-scheme: dark`. 0.6 s after the flip the canvas gradient is between the
  two palettes (a fade), and it is fully night by 3 s.
- Fake clock: 23:59:00 → 23:59:45 day → 00:00:16 night. 07:31:00 →
  07:31:45 night → 07:32:15 day. With `/api/weather` aborted, the page is night at
  06:29:30 and day at 06:30.
- Console clean. 73 tests pass.

Deviations:
- **Holiday line** is brick red `#c9655a` (as requested) through the existing
  `--holiday-ink` token, not the mockup's `#ff7a6b`. As in the day palette, it
  is red only when a holiday is set (`.has-holiday`). The empty state keeps the
  gold ink. Its label is at opacity .7 as in the mockup.
- **Background gradient**: `--bg-grad` is now built from three registered
  colour properties (`--bg-grad-from/-mid/-to`, `@property`), because a
  gradient cannot be transitioned. The day and night stop values are exactly
  the mockup's. The computed day gradient is unchanged (see the dump above).
- **Fade scope**: the transition is on `body, body *` (background-color,
  color, border-color, opacity), plus the three gradient stops on `html`.
  This is not just the top-level elements. Many children set their own
  colours, and those would otherwise cut. The photo crossfade's own,
  more-specific transition is unaffected. Inherited colours trail slightly, so
  the whole flip settles in about 3 s, not 1.5 s. SVG icon fills cut.
- **Mockup rules with no live target**: `.weather-metric` borders (the live
  metrics line has none) and `.photo .center` (mapped to `.photo-empty`).
  `.hour .symbol` maps to `--wx-fill: #8ec9e0` on the hourly icons only.
  Person heading/details have no rule of their own. They take `--gold-ink`, as
  in the mockup.
- `.chip` night colours override `.chip.cat` too (same specificity outcome as
  the mockup), so category chips become tinted rather than solid at night.
- A `NIGHT_MODE_START` later than sunrise (e.g. `23:00`) wraps past midnight.
  An unparseable value is treated as `00:00` (validated in config).
- `base.css` is 211 lines, just over the ~200 guideline. It stays in one file
  as requested.

---

## Deferred / ideas backlog

- ~~Photo source upgrade (shared album sync instead of manual folder drops)~~
  — done: Google Photos public-album sync (see Phase 2 deviations). Private
  albums (OAuth) still out of scope.
- Word-of-the-day or quote widget (fetch + cache, was liked on the old display)
- ~~Sunset/moon/UV row like the old display~~ — done: UV index, sunset and
  moon phase are in the weather panel (see Phase 2 deviations).
- Multiple layout profiles (e.g., school-morning layout on weekdays 6–8 am)
