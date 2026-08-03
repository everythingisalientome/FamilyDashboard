"""LAN-only admin API: fetcher health, manual refresh, and log access.

Read-only status (with source URLs and staleness), a fire-and-forget refresh
trigger, a way to clear an orphaned job row, and endpoints to view/download the
app's rotating log. No auth — this is a one-household LAN app.

Note: source URLs are capability URLs (anyone holding them can read the feed).
Showing them here is consistent with the LAN-only, one-household model; the admin
page is not meant to be exposed off the LAN.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app import config, logging_setup
from app.db import connect
from app.envelope import envelope
from app.fetchers import alerts, calendars, photos, weather

router = APIRouter()
log = logging.getLogger("dashboard.admin")

#: The schedulable fetchers, keyed by the name the refresh endpoint takes. Each
#: run() already swallows its own exceptions (the scheduler contract), so these
#: are safe to fire on a worker thread.
_FETCHERS: dict[str, Callable[[], None]] = {
    "weather": weather.run,
    "alerts": alerts.run,
    "calendars": calendars.run,
    "photos": photos.run,
}

#: Calendar jobs run on a nightly cron, not an interval, so "2x interval" is
#: meaningless — hold them fresh for a day plus slack before flagging stale.
_CALENDAR_STALE_SECONDS = 26 * 60 * 60

_MAX_TAIL_LINES = 5000


def _interval_for(job: str) -> int | None:
    """Configured refresh interval (seconds) for a fetch_meta job, if any."""
    if job.startswith("weather:"):
        return config.WEATHER_REFRESH_SECONDS
    if job.startswith("alerts:"):
        return config.ALERTS_REFRESH_SECONDS
    if job == "photos":
        return config.PHOTO_SYNC_REFRESH_SECONDS
    return None  # events:* are cron-scheduled — see _stale_after


def _stale_after(job: str) -> int:
    """Age (seconds) beyond which a job's last-good data counts as stale."""
    interval = _interval_for(job)
    return _CALENDAR_STALE_SECONDS if interval is None else interval * 2


def _age_seconds(iso: str | None) -> float | None:
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


def _feeds_by_job() -> dict[str, Any]:
    """Map each configured feed's job id to its CalendarFeed."""
    return {calendars.job_name(feed): feed for feed in config.CALENDAR_FEEDS}


def _active_jobs(feed_jobs: dict[str, Any]) -> set[str]:
    """Jobs that a currently-configured source is expected to produce."""
    active = {"weather:current", "weather:forecast", "weather:astro", "alerts:weather"}
    if config.PHOTOS_ALBUM_URL:
        active.add("photos")
    active.update(feed_jobs)
    return active


def _source_url(job: str, feed_jobs: dict[str, Any]) -> str:
    """The URL (or configured point) a job pulls from, for display."""
    point = f"{config.WEATHER_LAT},{config.WEATHER_LON}"
    if job in feed_jobs:
        return feed_jobs[job].url
    if job in ("weather:current", "weather:forecast"):
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

    feed_jobs = _feeds_by_job()
    active = _active_jobs(feed_jobs)

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
        age = _age_seconds(row["last_success_utc"])
        stale_after = _stale_after(job)
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
                "interval_seconds": _interval_for(job),
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
    feed_jobs = _feeds_by_job()
    if job in _active_jobs(feed_jobs):
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


# --- Logs ------------------------------------------------------------------


@router.get("/admin/logs")
def admin_logs(lines: int = Query(300, ge=1, le=_MAX_TAIL_LINES)) -> dict[str, Any]:
    """Tail of the current (today's) log file."""
    path = logging_setup.current_log_path()
    tail_lines, truncated = logging_setup.tail(path, lines)
    return envelope(
        {
            "file": path.name,
            "text": "\n".join(tail_lines),
            "line_count": len(tail_lines),
            "truncated": truncated,
            "exists": path.exists(),
        }
    )


@router.get("/admin/logs/files")
def admin_log_files() -> dict[str, Any]:
    """All log files (current + rotated), newest first, for the downloads list."""
    return envelope({"files": logging_setup.list_log_files()})


@router.get("/admin/logs/download")
def admin_log_download(name: str = Query(...)) -> FileResponse:
    """Download one log file as an attachment. Whitelisted to real log files."""
    if not logging_setup.is_log_file(name):
        raise HTTPException(status_code=400, detail="not a log file")
    path = (config.LOG_DIR / name).resolve()
    # Defence in depth: the resolved path must sit directly in LOG_DIR.
    if path.parent != config.LOG_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="text/plain", filename=name)
