"""Cached weather. Reads SQLite only — never touches api.weather.gov."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter

from app.config import DISPLAY_TZ, FORECAST_DAYS
from app.db import connect, last_success
from app.fetchers.weather import JOB_CURRENT, JOB_FORECAST
from app.envelope import envelope

router = APIRouter()

_MOON_NAMES = (
    "New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent",
)
_MOON_ICONS = ("🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘")
_SYNODIC_MONTH = 29.530588853
_KNOWN_NEW_MOON = date(2000, 1, 6)


@router.get("/weather")
def get_weather() -> dict[str, Any]:
    today = datetime.now(DISPLAY_TZ).date()

    with connect() as conn:
        current = conn.execute(
            "SELECT * FROM weather_current WHERE id = 1"
        ).fetchone()
        daily = conn.execute(
            """
            SELECT date_local, label, high_f, low_f, precip_pct, condition, icon
            FROM weather_daily
            WHERE date_local >= ?
            ORDER BY date_local
            LIMIT ?
            """,
            (today.isoformat(), FORECAST_DAYS + 1),  # +1: today, dropped below
        ).fetchall()
        astro = conn.execute(
            "SELECT sunrise, sunset, uv_index FROM weather_astro WHERE id = 1"
        ).fetchone()
        updated = last_success(conn, [JOB_CURRENT, JOB_FORECAST])

    days = [_day(row, today) for row in daily]

    # Today's own forecast still feeds the current-conditions block (high/low,
    # condition fallback), but the outlook strip starts at tomorrow — today is
    # already the big number above it.
    today_iso = today.isoformat()
    today_forecast = next((d for d in days if d["date"] == today_iso), {})
    forecast = [d for d in days if d["date"] != today_iso][:FORECAST_DAYS]

    current_out = _current(current, today_forecast)
    if current_out is not None:
        current_out.update(_astro(astro, today))

    return envelope(
        {
            "current": current_out,
            "daily": forecast,
        },
        last_updated=updated,
    )


def _astro(row: Any, today: date) -> dict[str, Any]:
    """UV index, sunset (as a clock time) and today's moon phase."""
    name, icon = _moon_phase(today)
    uv = row["uv_index"] if row is not None else None
    return {
        "uv_index": round(uv) if uv is not None else None,
        "sunset": _clock(row["sunset"]) if row is not None else None,
        "moon_phase": name,
        "moon_icon": icon,
    }


def _clock(iso: str | None) -> str | None:
    """``2026-08-02T20:14`` -> ``8:14 PM``."""
    if not iso:
        return None
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return None
    meridiem = "AM" if when.hour < 12 else "PM"
    return f"{when.hour % 12 or 12}:{when.minute:02d} {meridiem}"


def _moon_phase(day: date) -> tuple[str, str]:
    """Phase name + glyph for ``day``, from the days since a known new moon."""
    age = (day - _KNOWN_NEW_MOON).days % _SYNODIC_MONTH
    index = int(age / _SYNODIC_MONTH * 8 + 0.5) % 8
    return _MOON_NAMES[index], _MOON_ICONS[index]


def _current(row: Any, today_forecast: dict[str, Any]) -> dict[str, Any] | None:
    if row is None:
        return None

    # Airport stations often report a temperature with no condition text at
    # all; today's forecast is a better answer than a blank sky.
    return {
        "observed_utc": row["observed_utc"],
        "temp_f": _round(row["temp_f"]),
        "feels_like_f": _round(row["feels_like_f"]),
        "humidity_pct": _round(row["humidity_pct"]),
        "wind_mph": _round(row["wind_mph"]),
        "wind_dir": row["wind_dir"],
        "condition": row["condition"] or today_forecast.get("condition"),
        "icon": row["icon"] or today_forecast.get("icon") or "clear",
        "high_f": today_forecast.get("high_f"),
        "low_f": today_forecast.get("low_f"),
    }


def _day(row: Any, today: date) -> dict[str, Any]:
    day = date.fromisoformat(row["date_local"])
    if day == today:
        label = "Today"
    elif day == today + timedelta(days=1):
        label = "Tomorrow"
    else:
        label = row["label"]

    return {
        "date": row["date_local"],
        "label": label,
        "high_f": row["high_f"],
        "low_f": row["low_f"],
        "precip_pct": row["precip_pct"],
        "condition": _short_condition(row["condition"]),
        "icon": row["icon"] or "clear",
    }


def _short_condition(condition: str | None) -> str | None:
    """NWS chains phases with "then"; a forecast card only has room for one."""
    if not condition:
        return None
    return condition.split(" then ")[0].strip()


def _round(value: float | None) -> int | None:
    return None if value is None else round(value)
