"""Turn cached data into alert records for ``/api/alerts``.

Alerts show as a single shiny pill at the bottom of the photo panel that rotates
through the active alerts one at a time — never a layout-pushing banner. Every
record is ``{id, kind, tone, color, title, text}`` where ``tone`` is
``"red"`` (warnings / closures), ``"gold"`` (advisories / trash) or ``"custom"``
(a calendar's own ``color``); the frontend styles each tone as a shiny gradient.

Two families share the shape:

* **Weather** — active NWS alerts fetched into ``weather_alerts``. Only those
  matching ``ALERT_WEATHER_KEYWORDS`` (e.g. thunderstorm, heat advisory) or, as
  a safety net, at an ``ALERT_SAFETY_SEVERITIES`` level (so a Tornado / Flash
  Flood Warning is never dropped) qualify. Warnings are red, advisories gold.
* **Reminders** — closures (red), trash (gold) and per-calendar alerts (their
  configured colour), *derived* from the events cache with no fetch of their own.
"""

from datetime import date, datetime, timedelta
from typing import Any

from app.config import (
    ALERT_RED_SEVERITIES,
    ALERT_SAFETY_SEVERITIES,
    ALERT_WEATHER_KEYWORDS,
    CLOSURE_ALERT_CATEGORIES,
    TRASH_REMINDER_HOUR,
    TRASH_REMINDER_KEYWORDS,
)
from app.event_styles import categorize

#: Tone stacking order when the pill rotates: red first, then gold, then custom.
_TONE_RANK = {"red": 0, "gold": 1, "custom": 2}


def _record(
    id: str, kind: str, tone: str, title: str, text: str | None, color: str = ""
) -> dict[str, Any]:
    return {
        "id": id,
        "kind": kind,
        "tone": tone,
        "color": color,
        "title": title,
        "text": text,
    }


def _overlaps_today(row: Any, today_iso: str) -> bool:
    """True if the event's inclusive date span covers today."""
    return row["start_date_local"] <= today_iso <= row["end_date_local"]


# --- Weather (from the weather_alerts cache) -------------------------------


def weather_records(rows: list[Any], now_utc: datetime) -> list[dict[str, Any]]:
    """Qualifying active NWS alerts, dropping any already expired."""
    records: list[dict[str, Any]] = []
    for row in rows:
        if _expired(row["expires_utc"], now_utc):
            continue
        event = row["event"]
        severity = (row["severity"] or "Unknown").title()
        if not _qualifies(event, severity):
            continue
        records.append(
            _record(
                id=f"wx:{row['id']}",
                kind="weather",
                tone=_weather_tone(event, severity),
                title=event,
                text=row["headline"],
            )
        )
    return records


def _qualifies(event: str, severity: str) -> bool:
    low = event.lower()
    if any(kw.lower() in low for kw in ALERT_WEATHER_KEYWORDS):
        return True
    return severity in ALERT_SAFETY_SEVERITIES  # safety net for other warnings


def _weather_tone(event: str, severity: str) -> str:
    if severity in ALERT_RED_SEVERITIES or "warning" in event.lower():
        return "red"
    return "gold"


def _expired(expires_utc: str | None, now_utc: datetime) -> bool:
    if not expires_utc:
        return False  # no expiry given — trust the fetch to have dropped it
    try:
        return datetime.fromisoformat(expires_utc) <= now_utc
    except ValueError:
        return False


# --- Closures (red, on a weekday the closure covers) -----------------------


def closure_records(event_rows: list[Any], today: date) -> list[dict[str, Any]]:
    """Red alert for a school closure / early dismissal covering today.

    Reuses ``event_styles.categorize`` (no second keyword list) and only fires
    on weekdays, so a weekend inside a break — when 'no school' is trivially
    true — stays quiet.
    """
    if today.weekday() >= 5:  # Sat/Sun — nobody needs a 'no school' reminder
        return []
    today_iso = today.isoformat()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in event_rows:
        if not _overlaps_today(row, today_iso):
            continue
        category = categorize(row["title"])
        if category is None or category.key not in CLOSURE_ALERT_CATEGORIES:
            continue
        title = row["title"]
        if title in seen:
            continue
        seen.add(title)
        records.append(
            _record(f"closure:{today_iso}:{title}", "closure", "red", title, None)
        )
    return records


# --- Trash / recycling (gold; today, or tomorrow after 5 pm) ---------------


def trash_records(
    event_rows: list[Any], today: date, now_local: datetime
) -> list[dict[str, Any]]:
    """Gold alert for a pickup today, or tomorrow past ``TRASH_REMINDER_HOUR``."""
    if not TRASH_REMINDER_KEYWORDS:
        return []
    tomorrow = today + timedelta(days=1)
    show_tomorrow = now_local.hour >= TRASH_REMINDER_HOUR

    records: list[dict[str, Any]] = []
    for when, label in ((today, "today"), (tomorrow, "tomorrow")):
        if when == tomorrow and not show_tomorrow:
            continue
        titles = [
            row["title"]
            for row in event_rows
            if row["start_date_local"] == when.isoformat()
            and _matches_trash(row["title"])
        ]
        if not titles:
            continue
        records.append(
            _record(f"trash:{when.isoformat()}", "trash", "gold",
                    f"Trash {label}", titles[0])
        )
    return records


def _matches_trash(title: str | None) -> bool:
    low = (title or "").lower()
    return any(kw.lower() in low for kw in TRASH_REMINDER_KEYWORDS)


# --- Per-calendar alerts (a feed opted in via CAL_<KEY>_ALERT_COLOR) -------


def calendar_alert_records(
    event_rows: list[Any], alert_colors: dict[str, str], today: date
) -> list[dict[str, Any]]:
    """Any event from an alert-flagged feed that covers today, in its colour."""
    if not alert_colors:
        return []
    today_iso = today.isoformat()
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in event_rows:
        source = row["source"]
        color = alert_colors.get(source)
        if color is None or not _overlaps_today(row, today_iso):
            continue
        key = (source, row["title"])
        if key in seen:
            continue
        seen.add(key)
        records.append(
            _record(f"cal:{source}:{today_iso}:{row['title']}", "calendar",
                    "custom", row["title"], None, color=color)
        )
    return records


# --- Merge -----------------------------------------------------------------


def sort_key(record: dict[str, Any]) -> tuple[int, str]:
    """Rotate red first, then gold, then any custom colour; then by title."""
    return (_TONE_RANK.get(record["tone"], 3), record["title"])
