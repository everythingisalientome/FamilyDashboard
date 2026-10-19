"""Talking to api.weather.gov: requests, gridpoint lookup, unit conversion.

Everything here returns plain dicts. Deciding what to cache and writing it is
weather.py's job.
"""

import logging
from typing import Any

import httpx

from app.config import (
    FETCH_TIMEOUT_SECONDS,
    NWS_USER_AGENT,
    WEATHER_LAT,
    WEATHER_LON,
)
from app.fetchers.nws_icons import icon_key

log = logging.getLogger("dashboard.nws")

API = "https://api.weather.gov"

#: /points never changes for a fixed location, so it is resolved once per process.
_grid: dict[str, str] | None = None


def get(url: str) -> dict[str, Any]:
    headers = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers=headers
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def resolve_grid() -> dict[str, str]:
    """The forecast, hourly-forecast and station-list URLs for the configured coordinates."""
    global _grid
    if _grid is None:
        props = get(f"{API}/points/{WEATHER_LAT},{WEATHER_LON}")["properties"]
        _grid = {
            "forecast": props["forecast"],
            "hourly": props["forecastHourly"],
            "stations": props["observationStations"],
        }
        log.info("NWS grid resolved: %s", props.get("gridId"))
    return _grid


def station_ids(stations_url: str, limit: int = 4) -> list[str]:
    return [
        feature["properties"]["stationIdentifier"]
        for feature in get(stations_url)["features"]
    ][:limit]


def latest_observation(stations: list[str]) -> dict[str, Any] | None:
    """The first station in ``stations`` that actually reports a temperature.

    Individual stations drop offline or return a null reading routinely, which
    is why this walks the list instead of trusting the nearest one.
    """
    for station in stations:
        try:
            props = get(f"{API}/stations/{station}/observations/latest")["properties"]
        except Exception as exc:  # a single dead station is normal
            log.info("Station %s unavailable: %s", station, exc)
            continue
        temp_c = _value(props, "temperature")
        if temp_c is not None:
            return _observation_row(station, props, temp_c)
    return None


def _observation_row(
    station: str, props: dict[str, Any], temp_c: float
) -> dict[str, Any]:
    # Only one of heat index / wind chill is ever present, and never both.
    feels_c = _value(props, "heatIndex")
    if feels_c is None:
        feels_c = _value(props, "windChill")
    wind_kmh = _value(props, "windSpeed")

    return {
        "observed_utc": props.get("timestamp"),
        "temp_f": to_fahrenheit(temp_c),
        "feels_like_f": to_fahrenheit(feels_c if feels_c is not None else temp_c),
        "humidity_pct": _value(props, "relativeHumidity"),
        "wind_mph": round(wind_kmh * 0.621371, 1) if wind_kmh is not None else None,
        "wind_dir": compass(_value(props, "windDirection")),
        "condition": (props.get("textDescription") or "").strip() or None,
        "icon": icon_key(props.get("icon")),
        "station": station,
    }


def _value(props: dict[str, Any], key: str) -> float | None:
    """NWS wraps every measurement as ``{"value": x, "unitCode": ...}``."""
    entry = props.get(key)
    return entry.get("value") if isinstance(entry, dict) else None


def to_fahrenheit(celsius: float) -> float:
    return round(celsius * 9 / 5 + 32, 1)


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    points = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")
    return points[round(degrees / 22.5) % 16]
