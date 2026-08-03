# Family Wall Dashboard

A self-hosted family wall display. A Python backend on a Windows server
fetches, caches, and serves all data; a Raspberry Pi displays the dashboard in
Chromium kiosk mode over the LAN.

## Architecture principles

- **The Pi stays dumb.** It only loads one URL. All logic, fetching, and
  rendering decisions live on the server. Never suggest putting code on the Pi.
- **The dashboard page never calls external services.** It only talks to this
  server's `/api/*` endpoints, which serve cached data from SQLite. External
  fetching happens exclusively in scheduled background jobs.
- **Serve stale over serving nothing.** If a feed is unreachable, keep showing
  the last good data and expose a `last_updated` timestamp so the frontend can
  indicate staleness. The wall display must never show an error page or spinner.
- **This is a one-household app.** No auth, no multi-tenancy, no scaling
  concerns. LAN-only. Prefer the simplest solution that works.

## Stack

- Python 3.12, FastAPI, uvicorn
- APScheduler (runs inside the FastAPI process) for timed fetch jobs
- SQLite for the cache (`data/dashboard.db`), stdlib `sqlite3`, no ORM
- httpx for HTTP, icalendar for ICS parsing, BeautifulSoup4 for scraping
- Frontend: plain HTML/CSS/JS in `static/` — no framework, no build tools,
  no npm, ever. Single page, CSS grid layout, vanilla JS polling `/api/*`.
- Deployed as a Windows service via NSSM. Assume Windows paths and NSSM
  in any deployment instructions.

## Conventions

- One fetcher module per data source type in `app/fetchers/`. Each exposes a
  single `run()` function that fetches, parses, and writes to SQLite.
- Fetchers must be independent: one failing must not affect others. Wrap each
  job in try/except and log failures; never let an exception kill the scheduler.
- All timestamps stored in UTC, converted to America/New_York for display.
- API responses are JSON with a consistent envelope:
  `{"data": ..., "last_updated": "<ISO8601>"}`.
- Type hints on all functions. Keep files short; split before any file
  exceeds ~200 lines.
- Configuration (feed URLs, intervals, location) lives in `app/config.py`,
  secrets (LLM API key) in `.env` — never hardcoded.

## Commands

- Run dev server: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- The dashboard is then at `http://<server-ip>:8000/`

## Workflow

- The roadmap and per-phase specs are in PLAN.md. Implement one phase at a
  time. When a phase is complete, update PLAN.md: mark it done and note any
  deviations from the spec.
