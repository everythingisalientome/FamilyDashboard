"""Cache NWS current conditions and the daily forecast.

Current conditions and the forecast are recorded as separate jobs: the nearest
station drops out far more often than the gridpoint forecast does, and losing
one should not blank the other.
"""

import logging
from datetime import datetime
from typing import Any

from app.config import DISPLAY_TZ
from app.db import connect, record_attempt, record_failure, record_success
from app.fetchers import nws, openmeteo
from app.fetchers.nws_icons import icon_key

log = logging.getLogger("dashboard.weather")

JOB_CURRENT = "weather:current"
JOB_FORECAST = "weather:forecast"
JOB_ASTRO = "weather:astro"


def run() -> None:
    """Refresh weather. Never raises — the scheduler must survive."""
    # UV / sun times come from a different provider and don't need the NWS
    # grid, so they run first and independently of it.
    _refresh_astro()

    try:
        grid = nws.resolve_grid()
    except Exception as exc:
        log.exception("NWS gridpoint lookup failed")
        with connect() as conn:
            for job in (JOB_CURRENT, JOB_FORECAST):
                record_failure(conn, job, f"{type(exc).__name__}: {exc}")
        return

    for job, work in (
        (JOB_FORECAST, lambda: _refresh_forecast(grid["forecast"])),
        (JOB_CURRENT, lambda: _refresh_current(grid["stations"])),
    ):
        try:
            with connect() as conn:
                record_attempt(conn, job)
            work()
            with connect() as conn:
                record_success(conn, job)
        except Exception as exc:
            log.exception("%s failed", job)
            with connect() as conn:
                record_failure(conn, job, f"{type(exc).__name__}: {exc}")


# --- UV index & sun times (Open-Meteo) -------------------------------------


def _refresh_astro() -> None:
    with connect() as conn:
        record_attempt(conn, JOB_ASTRO)
    try:
        row = openmeteo.fetch_astro()
        with connect() as conn:
            conn.execute("DELETE FROM weather_astro")
            conn.execute(
                """
                INSERT INTO weather_astro (id, date_local, sunrise, sunset, uv_index)
                VALUES (1, :date_local, :sunrise, :sunset, :uv_index)
                """,
                row,
            )
            record_success(conn, JOB_ASTRO)
        log.info("Astro: UV %s, sunset %s", row["uv_index"], row["sunset"])
    except Exception as exc:
        log.exception("%s failed", JOB_ASTRO)
        with connect() as conn:
            record_failure(conn, JOB_ASTRO, f"{type(exc).__name__}: {exc}")


# --- Forecast --------------------------------------------------------------


def _refresh_forecast(forecast_url: str) -> None:
    periods = nws.get(forecast_url)["properties"]["periods"]
    days = _group_by_day(periods)
    if not days:
        raise ValueError("forecast contained no usable periods")

    with connect() as conn:
        conn.execute("DELETE FROM weather_daily")
        conn.executemany(
            """
            INSERT INTO weather_daily
                (date_local, label, high_f, low_f, precip_pct, condition, icon)
            VALUES (:date_local, :label, :high_f, :low_f, :precip_pct,
                    :condition, :icon)
            """,
            days,
        )
    log.info("Forecast: %d days", len(days))


def _group_by_day(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold NWS's alternating day/night periods into one row per calendar day.

    A night period starts at 6pm on its own day, so bucketing by the local
    date of ``startTime`` puts "Sunday" and "Sunday Night" together, which is
    the pairing the forecast text itself assumes.
    """
    buckets: dict[str, dict[str, Any]] = {}
    for period in periods:
        start = datetime.fromisoformat(period["startTime"]).astimezone(DISPLAY_TZ)
        key = start.date().isoformat()
        day = buckets.setdefault(
            key,
            {
                "date_local": key,
                "label": start.strftime("%a"),
                "high_f": None,
                "low_f": None,
                "precip_pct": None,
                "condition": None,
                "icon": None,
            },
        )

        if period.get("isDaytime"):
            day["high_f"] = period.get("temperature")
            # Daytime conditions describe the day; keep them over the night's.
            day["condition"] = period.get("shortForecast")
            day["icon"] = icon_key(period.get("icon"), is_daytime=True)
        else:
            day["low_f"] = period.get("temperature")
            if day["condition"] is None:
                day["condition"] = period.get("shortForecast")
                day["icon"] = icon_key(period.get("icon"), is_daytime=False)

        precip = (period.get("probabilityOfPrecipitation") or {}).get("value")
        if precip is not None:
            current = day["precip_pct"]
            day["precip_pct"] = precip if current is None else max(current, precip)

    return [buckets[key] for key in sorted(buckets)]


# --- Current conditions ----------------------------------------------------


def _refresh_current(stations_url: str) -> None:
    stations = nws.station_ids(stations_url)
    observation = nws.latest_observation(stations)
    if observation is None:
        raise ValueError(f"no station in {stations} reported a temperature")

    with connect() as conn:
        conn.execute("DELETE FROM weather_current")
        conn.execute(
            """
            INSERT INTO weather_current
                (id, observed_utc, temp_f, feels_like_f, humidity_pct,
                 wind_mph, wind_dir, condition, icon, station)
            VALUES (1, :observed_utc, :temp_f, :feels_like_f, :humidity_pct,
                    :wind_mph, :wind_dir, :condition, :icon, :station)
            """,
            observation,
        )
    log.info("Current: %s at %.0f°F", observation["station"], observation["temp_f"])
