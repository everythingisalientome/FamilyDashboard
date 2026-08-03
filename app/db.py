"""SQLite cache. Everything the display shows is read from here, never live.

One connection per call: the fetch jobs and request handlers run on different
threads, and at this traffic level opening a file handle costs nothing.
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import DATA_DIR, DB_PATH
from app.envelope import utc_now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id                INTEGER PRIMARY KEY,
    source            TEXT    NOT NULL,
    uid               TEXT,
    title             TEXT    NOT NULL,
    start_utc         TEXT    NOT NULL,
    end_utc           TEXT,
    start_date_local  TEXT    NOT NULL,
    end_date_local    TEXT    NOT NULL,
    start_time_local  TEXT,
    all_day           INTEGER NOT NULL DEFAULT 0,
    location          TEXT,
    description       TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_dates ON events (start_date_local, end_date_local);
CREATE INDEX IF NOT EXISTS idx_events_source ON events (source);

CREATE TABLE IF NOT EXISTS weather_current (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    observed_utc  TEXT,
    temp_f        REAL,
    feels_like_f  REAL,
    humidity_pct  REAL,
    wind_mph      REAL,
    wind_dir      TEXT,
    condition     TEXT,
    icon          TEXT,
    station       TEXT
);

CREATE TABLE IF NOT EXISTS weather_daily (
    date_local  TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    high_f      INTEGER,
    low_f       INTEGER,
    precip_pct  INTEGER,
    condition   TEXT,
    icon        TEXT
);

-- Today's UV index and sun times, from Open-Meteo (NWS serves neither).
CREATE TABLE IF NOT EXISTS weather_astro (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    date_local  TEXT,
    sunrise     TEXT,
    sunset      TEXT,
    uv_index    REAL
);

-- One row per fetch job, so the frontend and the Phase 5 admin page can tell
-- fresh data from data that merely survived a failure.
CREATE TABLE IF NOT EXISTS fetch_meta (
    job               TEXT PRIMARY KEY,
    last_attempt_utc  TEXT,
    last_success_utc  TEXT,
    last_error        TEXT
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """A connection with row access by name, committed on clean exit."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the schema. Safe to call on every startup."""
    with connect() as conn:
        conn.executescript(SCHEMA)


def record_attempt(conn: sqlite3.Connection, job: str) -> None:
    conn.execute(
        """
        INSERT INTO fetch_meta (job, last_attempt_utc) VALUES (?, ?)
        ON CONFLICT(job) DO UPDATE SET last_attempt_utc = excluded.last_attempt_utc
        """,
        (job, utc_now_iso()),
    )


def record_success(conn: sqlite3.Connection, job: str) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO fetch_meta (job, last_attempt_utc, last_success_utc, last_error)
        VALUES (?, ?, ?, NULL)
        ON CONFLICT(job) DO UPDATE SET
            last_attempt_utc = excluded.last_attempt_utc,
            last_success_utc = excluded.last_success_utc,
            last_error       = NULL
        """,
        (job, now, now),
    )


def record_failure(conn: sqlite3.Connection, job: str, error: str) -> None:
    conn.execute(
        """
        INSERT INTO fetch_meta (job, last_attempt_utc, last_error) VALUES (?, ?, ?)
        ON CONFLICT(job) DO UPDATE SET
            last_attempt_utc = excluded.last_attempt_utc,
            last_error       = excluded.last_error
        """,
        (job, utc_now_iso(), error[:500]),
    )


def last_success(conn: sqlite3.Connection, jobs: list[str]) -> str | None:
    """Oldest successful fetch across ``jobs`` — the age of the weakest link."""
    marks = ",".join("?" * len(jobs))
    row = conn.execute(
        f"SELECT MIN(last_success_utc) AS oldest FROM fetch_meta "  # noqa: S608
        f"WHERE job IN ({marks}) AND last_success_utc IS NOT NULL",
        jobs,
    ).fetchone()
    return row["oldest"] if row else None
