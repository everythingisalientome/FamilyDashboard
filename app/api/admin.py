"""LAN-only admin API: fetcher health and manual refresh.

Read-only status (with source URLs and staleness), a fire-and-forget refresh
trigger, and a way to clear an orphaned job row. The log endpoints live in
admin_logs.py. No auth — this is a one-household LAN app.

Note: source URLs are capability URLs (anyone holding them can read the feed).
Showing them here is consistent with the LAN-only, one-household model; the admin
page is not meant to be exposed off the LAN.
"""

import logging
import threading
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from app import config, staleness
from app.db import connect
from app.envelope import envelope
from app.fetchers import alerts, calendars, gcal, photos, weather

router = APIRouter()
log = logging.getLogger("dashboard.admin")

def _refresh_calendars() -> None:
    """"The calendars" to the user: the ICS feeds plus the Google family feed."""
    calendars.run()
    if config.GCAL_CALENDAR_ID:
        gcal.run()


#: The schedulable fetchers, keyed by the name the refresh endpoint takes. Each
#: run() already swallows its own exceptions (the scheduler contract), so these
#: are safe to fire on a worker thread.
_FETCHERS: dict[str, Callable[[], None]] = {
    "weather": weather.run,
    "alerts": alerts.run,
    "calendars": _refresh_calendars,
    "photos": photos.run,
}

# Staleness math (interval_for / stale_after / age_seconds / feeds_by_job /
# active_jobs) lives in app.staleness, shared with the dashboard stale-dot so
# both agree on what "stale" means.


def _source_url(job: str, feed_jobs: dict[str, Any]) -> str:
    """The URL (or configured point) a job pulls from, for display."""
    point = f"{config.WEATHER_LAT},{config.WEATHER_LON}"
    if job == gcal.JOB and job in feed_jobs:
        return config.GCAL_CALENDAR_ID
    if job in feed_jobs:
        return feed_jobs[job].url
    if job in ("weather:current", "weather:forecast", "weather:hourly"):
        return f"https://api.weather.gov/points/{point}"
    if job == "weather:astro":
        return (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={config.WEATHER_LAT}&longitude={config.WEATHER_LON}"
        )
    if job == "alerts:weather":
        return f"https://api.weather.gov/alerts/active?point={point}"
    if job == "photos":
        return config.PHOTOS_ALBUM_URL
    return ""


@router.get("/admin/status")
def admin_status() -> dict[str, Any]:
    """Every fetch job's last attempt/success/error, source URL and staleness."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT job, last_attempt_utc, last_success_utc, last_error "
            "FROM fetch_meta"
        ).fetchall()
    meta: dict[str, dict[str, Any]] = {r["job"]: dict(r) for r in rows}

    feed_jobs = staleness.feeds_by_job()
    active = staleness.active_jobs(feed_jobs)

    # A configured feed that has never fetched yet still deserves a row.
    for job, feed in feed_jobs.items():
        meta.setdefault(
            job,
            {
                "job": job,
                "last_attempt_utc": None,
                "last_success_utc": None,
                "last_error": None,
            },
        )

    jobs: list[dict[str, Any]] = []
    for job in sorted(meta):
        row = meta[job]
        age = staleness.age_seconds(row["last_success_utc"])
        stale_after = staleness.stale_after(job)
        feed = feed_jobs.get(job)
        jobs.append(
            {
                "job": job,
                "label": feed.label if feed else job,
                "source": _source_url(job, feed_jobs),
                "orphaned": job not in active,
                "last_attempt_utc": row["last_attempt_utc"],
                "last_success_utc": row["last_success_utc"],
                "last_error": row["last_error"],
                "age_seconds": age,
                "stale_after_seconds": stale_after,
                "stale": age is None or age > stale_after,
                "interval_seconds": staleness.interval_for(job),
            }
        )

    # Photo sync is only meaningful when an album URL is set; hide its button
    # otherwise so the page doesn't offer a no-op refresh.
    fetchers = [
        name
        for name in sorted(_FETCHERS)
        if name != "photos" or config.PHOTOS_ALBUM_URL
    ]
    return envelope({"jobs": jobs, "fetchers": fetchers})


@router.post("/admin/refresh/{fetcher}")
def admin_refresh(fetcher: str) -> dict[str, Any]:
    """Fire a fetcher's run() on a background thread and return immediately."""
    run = _FETCHERS.get(fetcher)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown fetcher: {fetcher}")

    def _worker() -> None:
        log.info("Manual refresh started: %s", fetcher)
        try:
            run()  # run() swallows its own errors, but a thread must never crash
        except Exception:
            log.exception("Manual refresh %s crashed", fetcher)
        else:
            log.info("Manual refresh finished: %s", fetcher)

    threading.Thread(target=_worker, name=f"refresh-{fetcher}", daemon=True).start()
    return envelope({"fetcher": fetcher, "status": "started"})


@router.delete("/admin/jobs/{job}")
def admin_delete_job(job: str) -> dict[str, Any]:
    """Clear a status row for a source that no longer exists.

    Refuses to delete a currently-active job (its row is recreated on the next
    fetch, so deleting it is pointless). For an orphaned ``events:<key>`` it also
    drops that feed's leftover events, so a removed calendar fully disappears.
    """
    feed_jobs = staleness.feeds_by_job()
    if job in staleness.active_jobs(feed_jobs):
        raise HTTPException(
            status_code=409, detail=f"{job} is an active job, not orphaned"
        )

    with connect() as conn:
        cur = conn.execute("DELETE FROM fetch_meta WHERE job = ?", (job,))
        removed_events = 0
        if job.startswith("events:"):
            source = job.split(":", 1)[1]
            ev = conn.execute("DELETE FROM events WHERE source = ?", (source,))
            removed_events = ev.rowcount
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"no such job: {job}")

    log.info("Cleared orphaned job %s (%d event rows)", job, removed_events)
    return envelope({"job": job, "removed_events": removed_events})
