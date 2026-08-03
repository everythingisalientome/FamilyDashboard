"""Active alerts: fetched NWS weather alerts plus derived reminders.

Reads SQLite only. The NWS half comes from the ``weather_alerts`` cache; the
reminders (closures, trash, per-calendar alerts) are computed here from the
events cache and ``config`` — no feed of their own. Expiry is applied at read
time, so an alert disappears on the next page poll rather than at the next fetch.
The frontend shows the result as a shiny pill on the photo panel that rotates
through the active alerts one at a time.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter

from app import alert_rules
from app.config import CALENDAR_FEEDS, DISPLAY_TZ
from app.db import connect, last_success
from app.envelope import envelope
from app.fetchers.alerts import JOB

router = APIRouter()

#: source -> alert colour, for feeds that opted in via CAL_<KEY>_ALERT_COLOR.
_ALERT_COLORS: dict[str, str] = {
    feed.key: feed.alert_color for feed in CALENDAR_FEEDS if feed.alert_color
}


@router.get("/alerts")
def get_alerts() -> dict[str, Any]:
    now_local = datetime.now(DISPLAY_TZ)
    now_utc = datetime.now(timezone.utc)
    today = now_local.date()
    tomorrow = today + timedelta(days=1)

    with connect() as conn:
        alert_rows = conn.execute(
            "SELECT id, event, severity, headline, expires_utc FROM weather_alerts"
        ).fetchall()
        # Events that overlap today or start tomorrow: enough for closures /
        # calendar alerts covering today and a trash pickup due tomorrow.
        event_rows = conn.execute(
            """
            SELECT source, title, start_date_local, end_date_local
            FROM events
            WHERE end_date_local >= ? AND start_date_local <= ?
            """,
            (today.isoformat(), tomorrow.isoformat()),
        ).fetchall()
        updated = last_success(conn, [JOB])

    records = [
        *alert_rules.weather_records(alert_rows, now_utc),
        *alert_rules.closure_records(event_rows, today),
        *alert_rules.trash_records(event_rows, today, now_local),
        *alert_rules.calendar_alert_records(event_rows, _ALERT_COLORS, today),
    ]
    records.sort(key=alert_rules.sort_key)

    return envelope({"alerts": records}, last_updated=updated)
