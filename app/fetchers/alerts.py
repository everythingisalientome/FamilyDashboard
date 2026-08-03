"""Cache active NWS weather alerts for the configured point.

One job, replace-all: every fetch swaps the whole ``weather_alerts`` table for
the current active set. A failed fetch leaves the previous rows in place (the
scheduler and this body both swallow the exception), so a network blip keeps
the last known alerts on the wall rather than clearing a real warning.

The rule-based reminders (closures, trash, countdowns) are *not* here — they
are derived from already-cached data at request time in ``api/alerts.py``.
"""

import logging
from typing import Any

from app.config import WEATHER_LAT, WEATHER_LON
from app.db import connect, record_attempt, record_failure, record_success
from app.fetchers import nws

log = logging.getLogger("dashboard.alerts")

JOB = "alerts:weather"


def run() -> None:
    """Refresh active NWS alerts. Never raises — the scheduler must survive."""
    with connect() as conn:
        record_attempt(conn, JOB)
    try:
        rows = _fetch_active()
    except Exception as exc:
        log.exception("%s failed", JOB)
        with connect() as conn:
            record_failure(conn, JOB, f"{type(exc).__name__}: {exc}")
        return

    with connect() as conn:
        conn.execute("DELETE FROM weather_alerts")
        if rows:
            conn.executemany(
                """
                INSERT INTO weather_alerts
                    (id, event, severity, headline, description,
                     onset_utc, expires_utc)
                VALUES (:id, :event, :severity, :headline, :description,
                        :onset_utc, :expires_utc)
                """,
                rows,
            )
        record_success(conn, JOB)
    log.info("Alerts: %d active", len(rows))


def _fetch_active() -> list[dict[str, Any]]:
    url = f"{nws.API}/alerts/active?point={WEATHER_LAT},{WEATHER_LON}"
    features = nws.get(url).get("features") or []
    rows: list[dict[str, Any]] = []
    for feature in features:
        row = _row(feature)
        if row is not None:
            rows.append(row)
    return rows


def _row(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties") or {}
    event = (props.get("event") or "").strip()
    alert_id = feature.get("id") or props.get("id")
    if not event or not alert_id:  # nothing worth showing without these
        return None
    # NWS gives "ends" when the hazard is expected to end and "expires" when the
    # alert message itself lapses; prefer the later of the two so we don't drop
    # a live warning early, falling back to whichever is present.
    ends = props.get("ends")
    expires = props.get("expires")
    expires_utc = max(x for x in (ends, expires) if x) if (ends or expires) else None
    return {
        "id": str(alert_id),
        "event": event,
        "severity": (props.get("severity") or "Unknown").strip() or "Unknown",
        "headline": (props.get("headline") or "").strip() or None,
        "description": (props.get("description") or "").strip() or None,
        "onset_utc": props.get("onset") or props.get("effective"),
        "expires_utc": expires_utc,
    }
