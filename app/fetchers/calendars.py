"""Fetch every configured ICS feed and cache the next 30 days of events.

The family feed (blank ``url``) is the Google Calendar API — see gcal.py.

Each feed is replaced in the database only after its own fetch and parse both
succeed, so one dead feed leaves the others — and its own last good data —
untouched on the wall.
"""

import logging
import sqlite3
from datetime import date, datetime
from typing import Any

import httpx

from app.config import (
    CALENDAR_FEEDS,
    DISPLAY_TZ,
    FETCH_TIMEOUT_SECONDS,
    CalendarFeed,
)
from app.db import connect, record_attempt, record_failure, record_success
from app.event_window import fetch_window
from app.fetchers.ics import parse_events

log = logging.getLogger("dashboard.calendars")


def job_name(feed: CalendarFeed) -> str:
    return f"events:{feed.key}"


def run() -> None:
    """Refresh all calendar feeds. Never raises — the scheduler must survive."""
    ics_feeds = [feed for feed in CALENDAR_FEEDS if feed.url]
    if not ics_feeds:
        log.warning("No ICS calendar feeds configured")
        return

    # Reach back past the 1st so the month grid's earlier cells and its
    # leading week from the previous month are populated too.
    start, end = fetch_window(datetime.now(DISPLAY_TZ).date())

    for feed in ics_feeds:
        try:
            _refresh_feed(feed, start, end)
        except Exception as exc:
            log.exception("Calendar feed %s failed", feed.key)
            with connect() as conn:
                record_failure(conn, job_name(feed), f"{type(exc).__name__}: {exc}")


def _refresh_feed(feed: CalendarFeed, start: date, end: date) -> None:
    with connect() as conn:
        record_attempt(conn, job_name(feed))

    text = _fetch(feed.url)
    rows = parse_events(text, start, end)

    with connect() as conn:
        replace_source(conn, feed.key, rows)
        record_success(conn, job_name(feed))

    log.info("Calendar %s: %d events through %s", feed.key, len(rows), end)


def _fetch(url: str) -> str:
    headers = {"User-Agent": "FamilyWallDashboard/1.0"}
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers=headers
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def replace_source(
    conn: sqlite3.Connection, source: str, rows: list[dict[str, Any]]
) -> None:
    """Swap in the new rows for one source inside a single transaction.

    ``person``/``kind`` are optional per row (only the Google feed sets them).
    """
    conn.execute("DELETE FROM events WHERE source = ?", (source,))
    conn.executemany(
        """
        INSERT INTO events (
            source, uid, title, start_utc, end_utc, start_date_local,
            end_date_local, start_time_local, all_day, location, description,
            person, kind
        ) VALUES (
            :source, :uid, :title, :start_utc, :end_utc, :start_date_local,
            :end_date_local, :start_time_local, :all_day, :location, :description,
            :person, :kind
        )
        """,
        [{"person": None, "kind": None, **row, "source": source} for row in rows],
    )
