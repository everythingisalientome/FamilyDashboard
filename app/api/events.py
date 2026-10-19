"""Cached calendar events. Reads SQLite only — never touches the ICS feeds."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.config import (
    CALENDAR_FEEDS,
    DISPLAY_TZ,
    EVENT_CACHE_DAYS,
    EVENT_HORIZON_DAYS,
    HIGHLIGHT_DAYS,
    HIGHLIGHT_KEYWORDS,
    PERSONS,
    RADAR_DAYS,
)
from app.db import connect, last_success
from app.envelope import envelope
from app.event_window import grid_start
from app.event_styles import EVENT_CATEGORIES, categorize
from app.events_derived import hero, is_excluded, radar, waste
from app.fetchers.calendars import job_name
from app.persons import display_color, persons_for

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

router = APIRouter()


@router.get("/events")
def get_events(
    days: int = Query(EVENT_HORIZON_DAYS, ge=1, le=365),
) -> dict[str, Any]:
    """Events overlapping now through ``days`` ahead.

    The window also reaches back to the start of the current month grid, since
    the display draws the whole month and its earlier days would otherwise be
    blank.
    """
    now = datetime.now(timezone.utc)
    today = now.astimezone(DISPLAY_TZ).date()
    window_start = grid_start(today)
    window_end = today + timedelta(days=days)
    # hero/radar/waste read everything cached ahead, whatever ``days`` asks.
    ahead = max(days, EVENT_CACHE_DAYS, RADAR_DAYS)
    read_end = today + timedelta(days=ahead)

    jobs = [job_name(feed) for feed in CALENDAR_FEEDS]
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT source, title, start_utc, end_utc, start_date_local,
                   end_date_local, start_time_local, all_day, location, person
            FROM events
            WHERE end_date_local >= ? AND start_date_local <= ?
            ORDER BY start_date_local, all_day DESC, start_utc, title
            """,
            (window_start.isoformat(), read_end.isoformat()),
        ).fetchall()
        updated = last_success(conn, jobs) if jobs else None
    # EVENT_EXCLUDE_KEYWORDS: dropped once, here, before anything derives from
    # the rows. The cache keeps them, so a keyword change needs no refetch.
    rows = [row for row in rows if not is_excluded(row["title"])]

    feed_colors = {f.key: f.color for f in CALENDAR_FEEDS}
    every = [_event(row, feed_colors) for row in rows]
    in_window = [e for e in every if e["start_date"] <= window_end.isoformat()]

    return envelope(
        {
            "today": today.isoformat(),
            "window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "sources": [
                {"key": f.key, "label": f.label, "color": f.color}
                for f in CALENDAR_FEEDS
            ],
            "categories": {
                c.key: {"color": c.color, "order": c.order}
                for c in EVENT_CATEGORIES
            },
            "highlights": _highlights(rows, today),
            "events": in_window,
            "persons": [
                {"key": p.key, "label": p.label, "color": p.color, "order": p.order}
                for p in PERSONS
            ],
            "hero": hero(every, today, now),
            "radar": radar(every, today),
            "waste": waste(every, today),
        },
        last_updated=updated,
    )


def _highlights(rows: list[Any], today: date) -> list[dict[str, str]]:
    """Upcoming keywords (next HIGHLIGHT_DAYS) that appear in an event title.

    Feeds the one-line ticker. It shows the matched keyword itself — not the
    full event title — so "…· Recycling · Garbage" reads simply as "Recycling".
    Matching is a case-insensitive substring, so keywords can be loose.
    """
    if not HIGHLIGHT_KEYWORDS:
        return []

    horizon = today + timedelta(days=HIGHLIGHT_DAYS)

    highlights: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        start = date.fromisoformat(row["start_date_local"])
        end = date.fromisoformat(row["end_date_local"])
        if end < today or start > horizon:
            continue

        title_low = row["title"].lower()
        matched = [kw for kw in HIGHLIGHT_KEYWORDS if kw.lower() in title_low]
        if not matched:
            continue

        when = max(start, today)  # an already-running span reads from today
        label = " · ".join(dict.fromkeys(kw.title() for kw in matched))
        key = (when.isoformat(), label)
        if key in seen:
            continue
        seen.add(key)
        highlights.append(
            {"date_label": f"{_MONTHS[when.month - 1]} {when.day}", "title": label}
        )
    return highlights[:10]


def _event(row: Any, feed_colors: dict[str, str]) -> dict[str, Any]:
    category = categorize(row["title"])
    persons = persons_for(row)
    color = display_color(
        row,
        persons,
        feed_colors.get(row["source"], ""),
        category.color if category else None,
    )
    return {
        "source": row["source"],
        "title": row["title"],
        "start_utc": row["start_utc"],
        "end_utc": row["end_utc"],
        "start_date": row["start_date_local"],
        "end_date": row["end_date_local"],
        "all_day": bool(row["all_day"]),
        "time_label": _time_label(row["start_time_local"], bool(row["all_day"])),
        "location": row["location"],
        "category": category.key if category else None,
        "persons": persons,
        "color": color,
    }


def _time_label(start_time_local: str | None, all_day: bool) -> str | None:
    """``18:30`` -> ``6:30 PM``; a flat hour drops the minutes."""
    if all_day or not start_time_local:
        return None
    hour, minute = (int(part) for part in start_time_local.split(":"))
    meridiem = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    if minute == 0:
        return f"{display_hour} {meridiem}"
    return f"{display_hour}:{minute:02d} {meridiem}"
