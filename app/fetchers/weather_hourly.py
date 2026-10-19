"""Cache the NWS hourly forecast (the gridpoint's ``/forecast/hourly``).

Not a fetcher of its own: weather.py calls ``refresh`` inside the
weather:forecast job, but records it as the separate weather:hourly job so a
failure here never blanks the daily forecast.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import connect
from app.fetchers import nws
from app.fetchers.nws_icons import icon_key

log = logging.getLogger("dashboard.weather")

#: How far ahead to keep. The page shows six slots; the rest is slack so a
#: run of failed fetches still has hours to serve.
KEEP_HOURS = 24


def refresh(hourly_url: str) -> None:
    periods = nws.get(hourly_url)["properties"]["periods"]
    rows = hourly_rows(periods, datetime.now(timezone.utc))
    if not rows:
        raise ValueError("hourly forecast contained no usable periods")

    with connect() as conn:
        conn.execute("DELETE FROM weather_hourly")
        conn.executemany(
            """
            INSERT INTO weather_hourly (start_utc, temp_f, condition, icon, precip_pct)
            VALUES (:start_utc, :temp_f, :condition, :icon, :precip_pct)
            """,
            rows,
        )
    log.info("Hourly: %d slots from %s", len(rows), rows[0]["start_utc"])


def hour_floor_utc(now: datetime) -> str:
    """``now`` truncated to the hour, in the format ``start_utc`` is stored in."""
    return now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()


def hourly_rows(periods: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """The periods from the current hour through the next ``KEEP_HOURS``."""
    start = datetime.fromisoformat(hour_floor_utc(now))
    end = start + timedelta(hours=KEEP_HOURS)

    rows: list[dict[str, Any]] = []
    for period in periods:
        when = datetime.fromisoformat(period["startTime"]).astimezone(timezone.utc)
        if not start <= when < end or period.get("temperature") is None:
            continue
        rows.append(
            {
                "start_utc": when.isoformat(),
                "temp_f": period["temperature"],
                "condition": period.get("shortForecast"),
                "icon": icon_key(period.get("icon"), is_daytime=period.get("isDaytime")),
                "precip_pct": (period.get("probabilityOfPrecipitation") or {}).get("value"),
            }
        )
    return rows
