"""APScheduler wiring. Runs inside the FastAPI process, one job per fetcher.

Every job body already swallows its own exceptions; the listener here is the
backstop that logs anything that still escapes so a bad job can never take the
scheduler down with it.
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import (
    ALERTS_REFRESH_SECONDS,
    CALENDAR_REFRESH_DAY,
    CALENDAR_REFRESH_HOUR,
    CALENDAR_REFRESH_MINUTE,
    DISPLAY_TZ,
    PHOTO_SYNC_REFRESH_SECONDS,
    PHOTOS_ALBUM_URL,
    WEATHER_REFRESH_SECONDS,
)
from app.fetchers import alerts, calendars, photos, weather

log = logging.getLogger("dashboard.scheduler")

#: Seconds after startup before the first run of each job, so an empty cache
#: fills immediately instead of waiting out a full interval — and so a feed
#: added to .env then restarted is fetched right away, not the next night.
STARTUP_DELAY = 2


def _on_job_error(event: JobExecutionEvent) -> None:
    log.error("Job %s raised", event.job_id, exc_info=event.exception)


def start() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,        # a missed run catches up once, not N times
            "max_instances": 1,      # a slow feed must not stack up
            "misfire_grace_time": 300,
        },
    )
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # Weather: short fixed interval, first run shortly after boot.
    scheduler.add_job(
        weather.run,
        IntervalTrigger(seconds=WEATHER_REFRESH_SECONDS),
        id="weather",
        next_run_time=_soon(),
    )
    log.info("Scheduled weather every %d s", WEATHER_REFRESH_SECONDS)

    # Alerts: short fixed interval like weather (active NWS alerts change fast
    # and expire on their own), first run shortly after boot.
    scheduler.add_job(
        alerts.run,
        IntervalTrigger(seconds=ALERTS_REFRESH_SECONDS),
        id="alerts",
        next_run_time=_soon(),
    )
    log.info("Scheduled alerts every %d s", ALERTS_REFRESH_SECONDS)

    # Calendars: nightly at a local wall-clock time (default every day 23:00;
    # day_of_week can pin it to one day for weekly). The cron trigger sets the
    # recurring schedule; next_run_time forces one run right after boot so an
    # empty or newly extended cache fills immediately.
    calendar_trigger = CronTrigger(
        day_of_week=CALENDAR_REFRESH_DAY,
        hour=CALENDAR_REFRESH_HOUR,
        minute=CALENDAR_REFRESH_MINUTE,
        timezone=DISPLAY_TZ,
    )
    scheduler.add_job(
        calendars.run,
        calendar_trigger,
        id="calendars",
        next_run_time=_soon(),
    )
    log.info(
        "Scheduled calendars at %02d:%02d %s (day_of_week=%s)",
        CALENDAR_REFRESH_HOUR,
        CALENDAR_REFRESH_MINUTE,
        DISPLAY_TZ,
        CALENDAR_REFRESH_DAY,
    )

    # Photos: only if a Google Photos album is configured. Same interval + boot
    # kick as weather, so a freshly set album fills the slideshow right away.
    if PHOTOS_ALBUM_URL:
        scheduler.add_job(
            photos.run,
            IntervalTrigger(seconds=PHOTO_SYNC_REFRESH_SECONDS),
            id="photos",
            next_run_time=_soon(),
        )
        log.info("Scheduled photos sync every %d s", PHOTO_SYNC_REFRESH_SECONDS)
    else:
        log.info("Photo sync disabled (PHOTOS_ALBUM_URL unset)")

    scheduler.start()
    return scheduler


def _soon() -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=STARTUP_DELAY)
