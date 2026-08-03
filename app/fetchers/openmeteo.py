"""Open-Meteo: the couple of fields NWS doesn't serve — UV index and sun times.

The National Weather Service API has no UV index and no sunrise/sunset, so this
one keyless call fills them in for the configured location. It is deliberately
tiny and kept apart from the NWS jobs so an Open-Meteo outage can't touch the
temperature or forecast.
"""

from typing import Any

import httpx

from app.config import FETCH_TIMEOUT_SECONDS, WEATHER_LAT, WEATHER_LON

_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_astro() -> dict[str, Any]:
    """Today's max UV index and local sunrise/sunset for the configured point."""
    params = {
        "latitude": WEATHER_LAT,
        "longitude": WEATHER_LON,
        "daily": "uv_index_max,sunrise,sunset",
        "timezone": "auto",
        "forecast_days": 1,
    }
    with httpx.Client(
        timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        response = client.get(_URL, params=params)
        response.raise_for_status()
        daily = response.json()["daily"]

    return {
        "date_local": daily["time"][0],
        "sunrise": daily["sunrise"][0],
        "sunset": daily["sunset"][0],
        "uv_index": daily["uv_index_max"][0],
    }
