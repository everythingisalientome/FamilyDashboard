"""ICS text in, display-ready event rows out.

Recurrence expansion is delegated to recurring_ical_events, which understands
RRULE/RDATE/EXDATE and the RECURRENCE-ID overrides that real calendars emit.
"""

import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import recurring_ical_events
from icalendar import Calendar

from app.config import DISPLAY_TZ

log = logging.getLogger("dashboard.ics")

#: "a, b, and c" / "a and b" — how ReCollect joins the day's pickup types.
_LIST_SEPARATOR = re.compile(r",\s*(?:and\s+)?|\s+and\s+")

#: The trailing " - concord" every ReCollect pickup name carries.
_MUNICIPALITY_SUFFIX = re.compile(r"\s+-\s+\S+\s*$")

_ACRONYMS = frozenset({"hhw"})


def parse_events(ics_text: str, start: date, end: date) -> list[dict[str, Any]]:
    """Expand ``ics_text`` into one row per occurrence between the two dates.

    ``end`` is inclusive. Raises if the payload is not parseable as a calendar;
    individual malformed events are skipped rather than failing the whole feed.
    """
    calendar = Calendar.from_ical(ics_text)
    occurrences = recurring_ical_events.of(calendar).between(
        start, end + timedelta(days=1)
    )

    rows: list[dict[str, Any]] = []
    for component in occurrences:
        try:
            row = _to_row(component)
        except Exception as exc:  # one bad VEVENT must not lose the feed
            log.warning("Skipping unparseable event: %s", exc)
            continue
        if row is not None:
            rows.append(row)

    rows.sort(key=lambda r: (r["start_utc"], r["title"]))
    return rows


def _to_row(component: Any) -> dict[str, Any] | None:
    if str(component.get("STATUS", "")).upper() == "CANCELLED":
        return None

    title = _clean_title(str(component.get("SUMMARY", "")).strip())
    if not title:
        return None

    dtstart = component["DTSTART"].dt
    dtend = component["DTEND"].dt if "DTEND" in component else None

    # A bare date means an all-day event, and its DTEND is exclusive.
    all_day = not isinstance(dtstart, datetime)
    if all_day:
        start_date = dtstart
        end_date = (dtend - timedelta(days=1)) if dtend else start_date
        if end_date < start_date:
            end_date = start_date
        start_utc = _midnight_utc(start_date)
        end_utc = _midnight_utc(end_date + timedelta(days=1))
        start_time_local = None
    else:
        start_local = _to_display_tz(dtstart)
        end_local = _to_display_tz(dtend) if isinstance(dtend, datetime) else None
        start_date = start_local.date()
        # An event ending exactly at midnight belongs to the day before.
        end_date = start_date
        if end_local:
            end_date = end_local.date()
            if end_local.time() == time(0, 0) and end_date > start_date:
                end_date -= timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc).isoformat()
        end_utc = end_local.astimezone(timezone.utc).isoformat() if end_local else None
        start_time_local = start_local.strftime("%H:%M")

    return {
        "uid": str(component.get("UID", "")) or None,
        "title": title,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "start_date_local": start_date.isoformat(),
        "end_date_local": end_date.isoformat(),
        "start_time_local": start_time_local,
        "all_day": int(all_day),
        "location": str(component.get("LOCATION", "")).strip() or None,
        "description": str(component.get("DESCRIPTION", "")).strip()[:500] or None,
    }


def _to_display_tz(value: datetime) -> datetime:
    """Floating times (no tzinfo) are, by RFC 5545, local to the viewer."""
    if value.tzinfo is None:
        return value.replace(tzinfo=DISPLAY_TZ)
    return value.astimezone(DISPLAY_TZ)


def _midnight_utc(day: date) -> str:
    return datetime.combine(day, time(0, 0), tzinfo=DISPLAY_TZ).astimezone(
        timezone.utc
    ).isoformat()


def _clean_title(title: str) -> str:
    """Shorten ReCollect's generated pickup summaries to the material names.

    "Yard waste - concord, bulky waste - concord, and garbage - concord"
    becomes "Yard Waste · Bulky Waste · Garbage" — grid cells are ~150px wide.
    The " - " requirement keeps ordinary titles that merely contain "and"
    (e.g. "Board of Education Work Session and Business Meeting") intact.
    """
    if " - " not in title:
        return title

    parts: list[str] = []
    for part in _LIST_SEPARATOR.split(title):
        part = _MUNICIPALITY_SUFFIX.sub("", part.strip()).strip()
        if part:
            parts.append(_title_case(part))
    if not parts:
        return title
    return " · ".join(dict.fromkeys(parts))  # dedupe, keep order


def _title_case(text: str) -> str:
    return " ".join(
        word.upper() if word.lower() in _ACRONYMS else word.capitalize()
        for word in text.split()
    )
