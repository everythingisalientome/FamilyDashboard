"""Shared fetch-staleness math.

"Stale" = a job's last successful fetch is older than 2x its refresh interval
(or a fixed ~26 h window for the nightly-cron calendar jobs, which have no
interval). Both the /admin status board and the dashboard stale-dot import this
so they agree on exactly what counts as stale.
"""

from datetime import datetime, timezone
from typing import Any

from app import config
from app.db import connect
from app.fetchers import calendars

#: Calendar jobs run on a nightly cron, not an interval, so "2x interval" is
#: meaningless — hold them fresh for a day plus slack before flagging stale.
CALENDAR_STALE_SECONDS = 26 * 60 * 60


def interval_for(job: str) -> int | None:
    """Configured refresh interval (seconds) for a fetch_meta job, if any."""
    if job.startswith("weather:"):
        return config.WEATHER_REFRESH_SECONDS
    if job.startswith("alerts:"):
        return config.ALERTS_REFRESH_SECONDS
    if job == "photos":
        return config.PHOTO_SYNC_REFRESH_SECONDS
    return None  # events:* are cron-scheduled — see stale_after


def stale_after(job: str) -> int:
    """Age (seconds) beyond which a job's last-good data counts as stale."""
    interval = interval_for(job)
    return CALENDAR_STALE_SECONDS if interval is None else interval * 2


def age_seconds(iso: str | None) -> float | None:
    """Seconds since ``iso`` (a stored UTC timestamp), or None if unset/bad."""
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds()


def feeds_by_job() -> dict[str, Any]:
    """Map each configured feed's job id to its CalendarFeed.

    Includes ``events:family`` (the Google feed) only when GCAL_CALENDAR_ID is
    set, since only then is it in CALENDAR_FEEDS.
    """
    return {calendars.job_name(feed): feed for feed in config.CALENDAR_FEEDS}


def active_jobs(feed_jobs: dict[str, Any] | None = None) -> set[str]:
    """Jobs that a currently-configured source is expected to produce."""
    if feed_jobs is None:
        feed_jobs = feeds_by_job()
    active = {
        "weather:current", "weather:forecast", "weather:hourly", "weather:astro",
        "alerts:weather",
    }
    if config.PHOTOS_ALBUM_URL:
        active.add("photos")
    active.update(feed_jobs)
    return active


def summary() -> dict[str, Any]:
    """Which *active* jobs are stale right now — powers the dashboard stale-dot.

    Only active jobs count: an orphaned row from a removed feed must not light
    up the wall. A never-succeeded active job counts as stale (its data is
    missing), which is exactly when the dot should show.
    """
    active = active_jobs()
    with connect() as conn:
        rows = conn.execute("SELECT job, last_success_utc FROM fetch_meta").fetchall()
    success = {r["job"]: r["last_success_utc"] for r in rows}

    stale = [
        job
        for job in sorted(active)
        if (age := age_seconds(success.get(job))) is None or age > stale_after(job)
    ]
    return {"stale": bool(stale), "stale_jobs": stale, "checked": len(active)}
