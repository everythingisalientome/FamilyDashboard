"""Extra checks for the admin page's dry-run (``APP_CONFIG_STRICT=1`` only).

At boot the config is lenient — a bad value falls back to its default so the
wall keeps running. Before the admin page *saves* a ``.env``, though, a typo
should be refused, so the dry-run imports ``app.config`` in strict mode and
these checks catch the values the lenient parsers would quietly ignore.
"""

import os
import re

from apscheduler.triggers.cron import CronTrigger

_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
_GROUP_RE = re.compile(r"^(?:CAL|PERSON|EVENT_STYLE)_.+_(COLOR|ALERT_COLOR|ORDER|URL)$")


def problems() -> list[str]:
    """Every invalid value in the environment, as human-readable lines."""
    found: list[str] = []
    for name, raw in sorted(os.environ.items()):
        value = raw.strip()
        match = _GROUP_RE.match(name)
        if not value or not match:
            continue
        kind = match.group(1)
        if kind.endswith("COLOR") and not _COLOR_RE.fullmatch(value):
            found.append(f"{name}={value!r} is not a #rrggbb colour")
        elif kind == "ORDER" and not value.lstrip("-").isdigit():
            found.append(f"{name}={value!r} is not a whole number")
        elif kind == "URL" and not value.startswith(("http://", "https://")):
            found.append(f"{name}={value!r} is not an http(s) URL")

    from app import config  # the values below are already parsed (strictly)

    if not -90 <= config.WEATHER_LAT <= 90:
        found.append(f"WEATHER_LAT={config.WEATHER_LAT} is outside -90..90")
    if not -180 <= config.WEATHER_LON <= 180:
        found.append(f"WEATHER_LON={config.WEATHER_LON} is outside -180..180")
    night = os.getenv("NIGHT_MODE_START", "").strip()
    if night and night != config.NIGHT_MODE_START:
        found.append(f"NIGHT_MODE_START={night!r} is not HH:MM (24h)")
    if not 0 <= config.TRASH_REMINDER_HOUR <= 23:
        found.append(f"TRASH_REMINDER_HOUR={config.TRASH_REMINDER_HOUR} is outside 0..23")
    try:  # the same trigger the scheduler builds at boot (a bad one crashes it)
        CronTrigger(
            day_of_week=config.CALENDAR_REFRESH_DAY,
            hour=config.CALENDAR_REFRESH_HOUR,
            minute=config.CALENDAR_REFRESH_MINUTE,
            timezone=config.DISPLAY_TZ,
        )
    except ValueError as exc:
        found.append(f"CALENDAR_REFRESH_DAY/HOUR/MINUTE: {exc}")
    return found


def check() -> None:
    """Raise with every problem listed, so the dry-run's stderr names them all."""
    found = problems()
    if found:
        raise ValueError("invalid settings:\n  " + "\n  ".join(found))
