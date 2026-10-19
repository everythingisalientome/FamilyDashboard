# Family Wall Dashboard

A self-hosted family wall display. A Python backend on an always-on machine
(a Windows server here) fetches, caches, and serves everything; a Raspberry Pi
displays the dashboard full-screen in Chromium kiosk mode over the LAN.

The wall is a light, per-person layout tuned for 1920×1080 and read from across
the room. It has a large clock, current conditions with the next six hours and
the next three days, a "next up" card for each child, the family's next events,
a colour-coded waste-pickup strip, a Sunday-first month calendar with a 30-day
"on the radar" footer, and a photo slideshow. The previous dark wall is still
served at `/v1`.

## Why

Off-the-shelf wall-display services worked but were hard to manage long-term
and couldn't get loud when something actually needed attention. This is a
one-household app: no accounts, no cloud, no scaling concerns — just the
simplest thing that runs on the LAN and is easy to change.

## Design principles

- **The Pi stays dumb.** It only loads one URL. All logic, fetching, and
  rendering decisions live on the server.
- **The page never calls external services.** It only talks to this server's
  `/api/*` endpoints, which serve cached data from SQLite. External fetching
  happens only in scheduled background jobs.
- **Serve stale over serving nothing.** If a feed is unreachable, the last good
  data stays on screen with a `last_updated` timestamp. The wall never shows an
  error page or spinner.
- **One household.** LAN-only, no auth, no multi-tenancy.

## Features

- **The wall (`/`)**: a light layout with a cyan canvas, an Oswald clock and
  DM Serif titles. The fonts are vendored, so the page never fetches from
  Google Fonts.
  - **Per-child "next up"**: one column per person (the first two by
    `PERSON_<KEY>_ORDER`). Each shows that child's next event and their **next
    holiday**, which differs per child because the school and the daycare close
    on different days. A person's events are the feeds that are wholly theirs
    plus title keyword matches.
  - **Family line**: the next one or two family-calendar events that match
    nobody.
  - **Waste strip**: the next pickup and its items. It turns green on a
    recycling week, orange on a bulky week, and is blue otherwise.
  - **Weather**: current conditions (°F with °C), H/L, feels-like, humidity
    and UV, plus six hourly slots from the next hour and a 3-day outlook.
  - **Month grid**: Sunday-first, 5 or 6 weeks as the month needs, with
    chips coloured by person or feed and an "on the radar" footer of keyword
    events in the next 30 days (multi-day spans collapsed).
- **The previous wall (`/v1`)**: the dark layout with the agenda, upcoming
  ticker, alerts pill, stale-dot and ambient background is unchanged. Open
  `/v1` to get it back.
- **Calendars** — the family **Google Calendar**, read through the Calendar API
  with a service account (changes made on a phone show at the next refresh, no
  hours-long ICS cache; an event's `person` tag puts it in that child's
  column), plus any number of ICS feeds (school district, ReCollect trash
  pickup, …) discovered from `.env`. Cached 90 days ahead (recurring events
  included; the grid lists 30) and merged with per-source colours. Titles
  matching `EVENT_EXCLUDE_KEYWORDS` (board meetings, bond forums) are hidden.
- **Photo → calendar importer** (`/admin` → *Add events*, phone-sized) — paste
  the JSON a chat model returns for a photographed daycare calendar or
  appointment email (prompt in `docs/event-extraction-prompt.md`). The server
  validates it, shows it for review, and writes it to the family Google
  Calendar with deterministic ids, so pasting the same JSON twice adds nothing.
  A rescheduled appointment can delete its predecessor. No model API is
  called by the app.
- **Event categories** — titles matching keyword categories are colour-coded
  (holiday = red, first-day/early-dismissal = gold, end-of-quarter = purple).
  Multi-day spans (a break week) tint their whole run of day cells as one block.
- **Weather** — current conditions from the US National Weather Service (temp
  with °C, feels-like, humidity, wind), plus UV index and sunrise/sunset from
  Open-Meteo and a locally-computed moon phase; a multi-day outlook strip.
- **Photos** — a slideshow from the local `photos/` folder, optionally synced
  from a public Google Photos shared album (no Google login required).
- **Ambient background** (`/v1`): a living illustrated scene (sky, sun/moon/stars,
  mountain, house, trees) behind the whole dashboard that tracks the **time of
  day** (anchored to real sunrise/sunset), the **current weather** (rain, snow,
  wind, thunderstorm/lightning, clouds, fog) and the **season**. Drawn locally as
  layered SVG + CSS, with optional pre-rendered art per season×phase; the panels
  are frosted glass so it shows through without hurting legibility.
- **Upcoming ticker** (`/v1`): a one-line strip of the next week's keyword highlights.
- **Alerts** (`/v1`): a shiny pill along the bottom of the photo panel rotates through
  active NWS weather alerts, school closures, trash reminders and per-calendar
  alerts, without ever pushing the layout.
- **Admin page** — `/admin` (LAN-only, no login) has four tabs. **Status**
  lists every feed with its last-fetch time, status, source URL and recent
  errors, plus a button to refresh any fetcher on demand. **Add events** is the
  importer. **Settings** edits `.env` itself: one sub-tab per section, each value
  read-only until you click ✎, add/remove calendar feeds and persons, and a
  drift banner for keys missing from `.env`. Every save is dry-run first and
  backed up (`data/env-backups/`). **Logs** views the current day's log and
  downloads older days. A "restart to apply" banner offers **Restart now** under
  the NSSM service.
- **Resilience** — every fetcher is independent and swallows its own errors;
  one dead feed never blanks the others or the page. The browser reloads itself
  nightly to shed any leaks. The app keeps a rotating daily log under
  `data/logs/`.

## Stack

- Python 3.12, [FastAPI](https://fastapi.tiangolo.com/) + uvicorn
- [APScheduler](https://apscheduler.readthedocs.io/) for timed fetch jobs
  (runs inside the FastAPI process)
- SQLite for the cache (`data/dashboard.db`), stdlib `sqlite3`, no ORM
- `httpx`, `icalendar` + `recurring-ical-events`, `python-dotenv`
- `google-api-python-client` + `google-auth` for the family Google Calendar
- Frontend: plain HTML/CSS/JS in `static/` — no framework, no build step, no npm

## Getting started

```bash
# 1. Clone and enter the project
git clone <your-repo-url> FamilyDashboard
cd FamilyDashboard

# 2. Create a virtualenv and install dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux
pip install -r requirements.txt

# 3. Configure — copy the example and fill in your feeds/location
copy .env.example .env              # 'cp' on macOS/Linux
# then edit .env

# 4. Run the dev server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://<server-ip>:8000/** full-screen. Drop images into `photos/` (or
set a Google Photos album URL in `.env`) and they appear in the slideshow.

## Configuration

Everything tunable lives in `.env` (see **`.env.example`** for the full,
commented list). Highlights:

| Variable | What it does |
|---|---|
| `GCAL_CALENDAR_ID` / `GCAL_SERVICE_ACCOUNT_FILE` | The family Google Calendar (shown as feed `family`; `CAL_FAMILY_LABEL/_COLOR/_ORDER` still style it) and the service-account key, default `data/gcal-sa.json`. Setup in [docs/deployment.md](docs/deployment.md). |
| `CAL_<KEY>_URL` / `_LABEL` / `_COLOR` / `_ORDER` | Define an ICS calendar feed. Add a calendar by adding a new block and restarting. |
| `CALENDAR_REFRESH_DAY` / `_HOUR` / `_MINUTE` | When calendars refresh (`*` = nightly; a weekday name = weekly). |
| `WEATHER_LAT` / `WEATHER_LON` / `NWS_USER_AGENT` | Weather location and NWS contact string. |
| `FORECAST_DAYS`, `WEATHER_REFRESH_SECONDS` | Forecast length (not counting today) and refresh interval. |
| `PHOTOS_ALBUM_URL` | Public Google Photos shared album to sync (blank = manual `photos/` only). |
| `PHOTO_INTERVAL_SECONDS` | Seconds each photo shows in the slideshow. |
| `EVENT_STYLE_<KEY>_KEYWORDS` / `_COLOR` / `_ORDER` | Extend/retune the colour categories. |
| `HIGHLIGHT_KEYWORDS`, `HIGHLIGHT_DAYS` | Which upcoming events feed the `/v1` ticker, and how far ahead. |
| `PERSON_<KEY>_LABEL` / `_COLOR` / `_ORDER` / `_FEEDS` / `_KEYWORDS` | Define a household member for the wall's "next up" columns: feeds that are wholly theirs, plus title keywords. The first two by `_ORDER` get a column. |
| `PERSON_COLOR_FEEDS`, `FAMILY_FEEDS`, `HERO_HOLIDAY_CATEGORIES` | Which feeds take a person's colour, which feed the family line, and which colour categories count as a "holiday". |
| `RADAR_KEYWORDS`, `RADAR_DAYS` | Which events appear in the month's "on the radar" footer, and how far ahead (default 30 days). |
| `WASTE_RECYCLE_KEYWORDS`, `WASTE_BULKY_KEYWORDS` | Pickup-title words that make the waste strip a recycling week (green) or a bulky week (orange). |
| `LOG_DIR`, `LOG_LEVEL`, `LOG_RETENTION_DAYS` | Where the rotating app log is written, its level, and how many past days to keep. |

`.env` is git-ignored — it holds capability URLs (calendar/photo share links)
that anyone with them can read, so it is never committed. Feed health and recent
errors are visible at **`/admin`**, which can also edit `.env` (dry-run checked,
backed up) and restart the service; changes take effect on restart.

## Project layout

```
app/
  main.py            FastAPI entrypoint (serves /api, /admin, /photos, /, /v1)
  config/            settings package, read from .env (feeds, persons, weather,
                     alerts, display); `from app.config import X`
  persons.py         which person(s) an event belongs to, and its chip colour
  events_derived.py  hero / radar / waste blocks for /api/events
  scheduler.py       APScheduler wiring for the fetch jobs
  db.py              SQLite schema + cache helpers
  logging_setup.py   root logging + the daily-rotating app log
  event_styles.py    keyword → colour category engine
  api/               /api/* endpoints (events, weather, photos, settings, admin)
  fetchers/          one module per data source (calendars, weather, photos, ...)
static/              the pages (HTML/CSS/JS, no build)
  v2.html            the wall at /  (css/v2/, js/v2/)
  index.html         the previous wall at /v1  (css/, js/)
  admin.html         /admin
  fonts/             vendored Oswald, DM Sans, DM Serif Display (woff2)
tests/               pytest (python -m pytest)
photos/              slideshow images (git-ignored; drop files or sync an album)
data/                SQLite cache + logs/ (git-ignored, created on first run)
scripts/             NSSM install/uninstall + background-image compressor
docs/                deployment guide, v2 mockup + reference screenshots
PLAN.md              phased roadmap and per-phase build notes
```

## Deployment

Runs as an always-on Windows service via [NSSM](https://nssm.cc/), with the Pi
booting straight into `chromium --kiosk http://<server-ip>:8000/`. From an
elevated PowerShell in the project root:

```powershell
.\scripts\install-service.ps1
```

See **[docs/deployment.md](docs/deployment.md)** for prerequisites (NSSM),
options, logs, updates, and the manual-install equivalents. The Pi kiosk
checklist is tracked in **[PLAN.md](PLAN.md)** (Phase 5).

## Roadmap

Built in phases — see **[PLAN.md](PLAN.md)** for the full plan and the build
notes for each phase. Done: Phases 1–3 (the dashboard, calendars, weather,
photos and alerts), Phase 4 (photo → calendar: the Google Calendar feed and
JSON importer), Phase 6 (the animated ambient background) and Phase 7 (the
light per-person layout, now the default wall). Phase 5 deployment polish is
complete (Windows service, Pi kiosk, admin page with feed health, logs and
tabbed `.env` editing with a restart banner, and the stale-dot).

---

*Personal one-household project. No warranty; not affiliated with Google,
Open-Meteo, or the National Weather Service.*
