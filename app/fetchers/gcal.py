"""Read the family Google Calendar through the API with a service account.

The ICS "secret address" is cached by Google for hours; the API is immediate,
so an event added on a phone shows at the next refresh. Stored under source
``family`` in the same events-row shape as the ICS feeds. On any failure the
existing rows stay put (serve stale) and the error lands in fetch_meta.

Timeout: the service is built over an ``httplib2.Http(timeout=...)`` wrapped in
``AuthorizedHttp``, so every API call (and the token refresh) is bounded by
FETCH_TIMEOUT_SECONDS without touching the process-wide socket default.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from app.config import (
    DISPLAY_TZ,
    DISPLAY_TZ_NAME,
    FETCH_TIMEOUT_SECONDS,
    GCAL_CALENDAR_ID,
    GCAL_FEED_KEY,
    GCAL_SCOPES,
    GCAL_SERVICE_ACCOUNT_FILE,
)
from app.db import connect, record_attempt, record_failure, record_success
from app.event_window import fetch_window
from app.fetchers.calendars import replace_source
from app.fetchers.ics import time_fields

log = logging.getLogger("dashboard.gcal")

JOB = f"events:{GCAL_FEED_KEY}"

#: Events per API page (Google's own cap is 2500; 250 is its default maximum).
_PAGE_SIZE = 250

#: Hard stop on page-following, so a misbehaving token can't loop forever.
_MAX_PAGES = 20


def run() -> None:
    """Refresh the family calendar. Never raises — the scheduler must survive."""
    try:
        reason = _config_problem()
        if reason:
            log.warning("Calendar %s skipped: %s", GCAL_FEED_KEY, reason)
            with connect() as conn:
                record_failure(conn, JOB, reason)
            return

        with connect() as conn:
            record_attempt(conn, JOB)

        start, end = fetch_window(datetime.now(DISPLAY_TZ).date())
        items = fetch_items(_build_service(), start, end)
        rows = [row for item in items if (row := to_row(item)) is not None]
        rows.sort(key=lambda r: (r["start_utc"], r["title"]))

        with connect() as conn:
            replace_source(conn, GCAL_FEED_KEY, rows)
            record_success(conn, JOB)
        log.info("Calendar %s: %d events through %s", GCAL_FEED_KEY, len(rows), end)
    except Exception as exc:
        log.exception("Calendar feed %s failed", GCAL_FEED_KEY)
        try:
            with connect() as conn:
                record_failure(conn, JOB, f"{type(exc).__name__}: {exc}")
        except Exception:
            log.exception("Could not record %s failure", JOB)


def _config_problem() -> str | None:
    if not GCAL_CALENDAR_ID:
        return "GCAL_CALENDAR_ID is not set"
    if not GCAL_SERVICE_ACCOUNT_FILE.is_file():
        return f"service account key not found: {GCAL_SERVICE_ACCOUNT_FILE}"
    return None


def _build_service() -> Any:
    """A Calendar v3 client over a timeout-bounded, authorised httplib2.

    Imported lazily so a deploy that forgot ``pip install -r requirements.txt``
    still boots the wall; this one feed just records the ImportError.
    """
    import httplib2
    from google.oauth2 import service_account
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_file(
        str(GCAL_SERVICE_ACCOUNT_FILE), scopes=list(GCAL_SCOPES)
    )
    http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=FETCH_TIMEOUT_SECONDS))
    return build("calendar", "v3", http=http, cache_discovery=False)


def fetch_items(service: Any, start: date, end: date) -> list[dict[str, Any]]:
    """Every expanded event from ``start`` through ``end`` (inclusive), all pages."""
    params: dict[str, Any] = {
        "calendarId": GCAL_CALENDAR_ID,
        "timeMin": datetime.combine(start, time(0, 0), tzinfo=DISPLAY_TZ).isoformat(),
        # timeMax is exclusive: midnight after ``end`` keeps the whole last day.
        "timeMax": datetime.combine(
            end + timedelta(days=1), time(0, 0), tzinfo=DISPLAY_TZ
        ).isoformat(),
        "singleEvents": True,
        "orderBy": "startTime",
        "timeZone": DISPLAY_TZ_NAME,
        "maxResults": _PAGE_SIZE,
    }
    items: list[dict[str, Any]] = []
    for _ in range(_MAX_PAGES):
        page = service.events().list(**params).execute()
        items.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            return items
        params["pageToken"] = token
    log.warning("Calendar %s: stopped after %d pages", GCAL_FEED_KEY, _MAX_PAGES)
    return items


def to_row(item: dict[str, Any]) -> dict[str, Any] | None:
    """One API event -> one events row, or None to skip it.

    Gmail-created events (``eventType: fromGmail``) are kept — they are real
    appointments. Person/kind come from the importer's private tags.
    """
    if item.get("status") == "cancelled":
        return None
    start, end = item.get("start") or {}, item.get("end") or {}
    if "date" in start:  # all-day; Google's end.date is exclusive, like ICS
        dtstart: date | datetime = date.fromisoformat(start["date"])
        dtend: date | datetime | None = (
            date.fromisoformat(end["date"]) if "date" in end else None
        )
    elif "dateTime" in start:
        dtstart = datetime.fromisoformat(start["dateTime"])
        dtend = datetime.fromisoformat(end["dateTime"]) if "dateTime" in end else None
    else:
        log.warning("Skipping event %s with no start", item.get("id"))
        return None

    private = (item.get("extendedProperties") or {}).get("private") or {}
    return {
        "uid": item.get("id"),
        "title": (item.get("summary") or "").strip() or "(No title)",
        **time_fields(dtstart, dtend),
        "location": (item.get("location") or "").strip() or None,
        "description": (item.get("description") or "").strip() or None,
        "person": (private.get("person") or "").strip().lower() or None,
        "kind": (private.get("kind") or "").strip() or None,
    }
