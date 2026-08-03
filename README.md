# Family Wall Dashboard

A self-hosted family wall display. A Python backend on an always-on machine
(a Windows server here) fetches, caches, and serves everything; a Raspberry Pi
displays the dashboard full-screen in Chromium kiosk mode over the LAN.

The wall shows a photo slideshow with the time and date, a month calendar with
colour-coded events, an upcoming-events agenda, a keyword "upcoming" ticker, and
current conditions plus a multi-day forecast — all on a dark, always-on layout
tuned for 1920×1080 viewed from across a room.

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

- **Calendars** — any number of ICS feeds (Google Calendar, school district,
  ReCollect trash pickup, …), discovered from `.env`, expanded 30 days ahead
  (recurring events included), merged with per-source colours.
- **Event categories** — titles matching keyword categories are colour-coded
  (holiday = red, first-day/early-dismissal = gold, end-of-quarter = purple).
  Multi-day spans (a break week) tint their whole run of day cells as one block.
- **Weather** — current conditions from the US National Weather Service (temp
  with °C, feels-like, humidity, wind), plus UV index and sunrise/sunset from
  Open-Meteo and a locally-computed moon phase; a multi-day outlook strip.
- **Photos** — a slideshow from the local `photos/` folder, optionally synced
  from a public Google Photos shared album (no Google login required).
- **Upcoming ticker** — a one-line strip of the next week's keyword highlights.
- **Resilience** — every fetcher is independent and swallows its own errors;
  one dead feed never blanks the others or the page. The browser reloads itself
  nightly to shed any leaks.

## Stack

- Python 3.12, [FastAPI](https://fastapi.tiangolo.com/) + uvicorn
- [APScheduler](https://apscheduler.readthedocs.io/) for timed fetch jobs
  (runs inside the FastAPI process)
- SQLite for the cache (`data/dashboard.db`), stdlib `sqlite3`, no ORM
- `httpx`, `icalendar` + `recurring-ical-events`, `python-dotenv`
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
| `CAL_<KEY>_URL` / `_LABEL` / `_COLOR` / `_ORDER` | Define a calendar feed. Add a calendar by adding a new block and restarting. |
| `CALENDAR_REFRESH_DAY` / `_HOUR` / `_MINUTE` | When calendars refresh (`*` = nightly; a weekday name = weekly). |
| `WEATHER_LAT` / `WEATHER_LON` / `NWS_USER_AGENT` | Weather location and NWS contact string. |
| `FORECAST_DAYS`, `WEATHER_REFRESH_SECONDS` | Forecast length (not counting today) and refresh interval. |
| `PHOTOS_ALBUM_URL` | Public Google Photos shared album to sync (blank = manual `photos/` only). |
| `PHOTO_INTERVAL_SECONDS` | Seconds each photo shows in the slideshow. |
| `EVENT_STYLE_<KEY>_KEYWORDS` / `_COLOR` / `_ORDER` | Extend/retune the colour categories. |
| `HIGHLIGHT_KEYWORDS`, `HIGHLIGHT_DAYS` | Which upcoming events feed the ticker, and how far ahead. |

`.env` is git-ignored — it holds capability URLs (calendar/photo share links)
that anyone with them can read, so it is never committed.

## Project layout

```
app/
  main.py            FastAPI entrypoint (serves /api, /photos, /)
  config.py          all settings, read from .env with sensible defaults
  scheduler.py       APScheduler wiring for the fetch jobs
  db.py              SQLite schema + cache helpers
  event_styles.py    keyword → colour category engine
  api/               /api/* endpoints (events, weather, photos, settings)
  fetchers/          one module per data source (calendars, weather, photos, ...)
static/              the single-page dashboard (HTML/CSS/JS, no build)
photos/              slideshow images (git-ignored; drop files or sync an album)
data/                SQLite cache (git-ignored, created on first run)
PLAN.md              phased roadmap and per-phase build notes
```

## Deployment

Intended to run as a Windows service via [NSSM](https://nssm.cc/), with the Pi
booting straight into `chromium --kiosk http://<server-ip>:8000/`. The detailed
service/kiosk checklist is tracked in **[PLAN.md](PLAN.md)** (Phase 5).

## Roadmap

Built in phases — see **[PLAN.md](PLAN.md)** for the full plan and the build
notes for each phase. Phases 1–2 (the dashboard, calendars, weather, photos)
are done; alerts, a scrape/LLM pipeline, and deployment polish are next.

---

*Personal one-household project. No warranty; not affiliated with Google,
Open-Meteo, or the National Weather Service.*
