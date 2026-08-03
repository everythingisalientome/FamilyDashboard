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

## Phase 4 — Scrape + LLM pipeline  [ ]

**Goal:** Dynamic data from sites that offer no feed.

**Build:**
- `fetchers/scraper.py`: per-source config (URL, CSS selector scope, prompt).
  BeautifulSoup extracts the relevant HTML region; an LLM call converts it to
  JSON matching a declared schema; response is validated against that schema
  before it is stored — invalid output keeps the previous good data.
- Runs once or twice daily per source. API key read from `.env`.
- First source: TBD (candidate: school lunch menu or community events page).
- `GET /api/scraped/<source>` endpoint; simple frontend card per source.

**Done when:** One scraped source displays reliably for a week, including
surviving at least one source-page change without showing garbage.

---

## Phase 5 — Manageability & deployment polish  [ ]

**Goal:** The reason we moved off the old service: easy to manage long-term.

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

## Deferred / ideas backlog

- ~~Photo source upgrade (shared album sync instead of manual folder drops)~~
  — done: Google Photos public-album sync (see Phase 2 deviations). Private
  albums (OAuth) still out of scope.
- Word-of-the-day or quote widget (fetch + cache, was liked on the old display)
- ~~Sunset/moon/UV row like the old display~~ — done: UV index, sunset and
  moon phase are in the weather panel (see Phase 2 deviations).
- Multiple layout profiles (e.g., school-morning layout on weekdays 6–8 am)
