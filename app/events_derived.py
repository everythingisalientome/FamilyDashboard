"""The v2 wall's derived blocks on /api/events: hero, radar and waste.

Pure functions over the API's own event dicts (``source``, ``title``,
``start_date``, ``end_date``, ``all_day``, ``start_utc``, ``end_utc``,
``category``, ``persons``), which arrive in chronological order — start date,
all-day first, then start time — so "earliest" is simply "first in the list".
"""

from collections.abc import Collection, Mapping
from datetime import date, datetime, timedelta
from typing import Any

from app.alert_rules import matches_trash
from app.config import (
    CALENDAR_FEEDS,
    EVENT_EXCLUDE_KEYWORDS,
    FAMILY_FEEDS,
    HERO_HOLIDAY_CATEGORIES,
    PERSONS,
    RADAR_DAYS,
    RADAR_KEYWORDS,
    WASTE_BULKY_KEYWORDS,
    WASTE_RECYCLE_KEYWORDS,
    Person,
)

Event = dict[str, Any]

#: Most entries the "On the radar" footer can hold.
RADAR_MAX = 8

#: Feed key -> CAL_<KEY>_CLOSED_LABEL, for the feeds that set one.
CLOSED_LABELS: dict[str, str] = {f.key: f.closed_label for f in CALENDAR_FEEDS if f.closed_label}


def is_excluded(title: str | None, keywords: tuple[str, ...] = EVENT_EXCLUDE_KEYWORDS) -> bool:
    """True when ``title`` contains an exclusion keyword (case-insensitive substring)."""
    low = (title or "").lower()
    return any(k.lower() in low for k in keywords)


def is_upcoming(event: Event, today: date, now: datetime) -> bool:
    """All-day: not yet past its last day. Timed: not yet ended."""
    if event["all_day"]:
        return event["end_date"] >= today.isoformat()
    ends = event["end_utc"] or event["start_utc"]
    return datetime.fromisoformat(ends) >= now


def closed_title(
    event: Event,
    labels: Mapping[str, str] = CLOSED_LABELS,
    holiday_categories: Collection[str] = HERO_HOLIDAY_CATEGORIES,
) -> str:
    """Hero/radar title: "<label> – <title before its first ':'>" for a holiday
    from a feed with a closed label, else the raw title."""
    label = labels.get(event["source"])
    if not label or event["category"] not in holiday_categories:
        return event["title"]
    return f"{label} – {event['title'].split(':', 1)[0].strip()}"


def _first(events: list[Event], count: int = 1) -> list[Event | None]:
    """The first ``count`` events, padded with None."""
    return (events[:count] + [None] * count)[:count]


# --- Hero ------------------------------------------------------------------


def hero(
    events: list[Event],
    today: date,
    now: datetime,
    roster: tuple[Person, ...] = PERSONS,
    family_feeds: Collection[str] = FAMILY_FEEDS,
    holiday_categories: Collection[str] = HERO_HOLIDAY_CATEGORIES,
    closed_labels: Mapping[str, str] = CLOSED_LABELS,
) -> dict[str, Any]:
    """Per-person NEXT UP / NEXT HOLIDAY for the first two persons, plus the
    family line (family-feed events that matched nobody).

    NEXT UP skips holidays — they already show on the NEXT HOLIDAY line, whose
    event carries its closed-label title (a copy; the grid's event is untouched).
    """
    upcoming = [e for e in events if is_upcoming(e, today, now)]

    columns: list[dict[str, Any]] = []
    for person in roster[:2]:
        pool = [e for e in upcoming if person.key in e["persons"]]
        holidays = [e for e in pool if e["category"] in holiday_categories]
        (nxt,) = _first([e for e in pool if e["category"] not in holiday_categories])
        (holiday,) = _first(holidays)
        if holiday:
            holiday = {**holiday, "title": closed_title(holiday, closed_labels, holiday_categories)}
        columns.append({"key": person.key, "next": nxt, "next_holiday": holiday})

    family = [e for e in upcoming if e["source"] in family_feeds and not e["persons"]]
    nxt, following = _first(family, 2)
    return {"persons": columns, "family": {"next": nxt, "following": following}}


# --- On the radar ----------------------------------------------------------


def radar(
    events: list[Event],
    today: date,
    days: int = RADAR_DAYS,
    keywords: tuple[str, ...] = RADAR_KEYWORDS,
    closed_labels: Mapping[str, str] = CLOSED_LABELS,
    holiday_categories: Collection[str] = HERO_HOLIDAY_CATEGORIES,
) -> list[dict[str, Any]]:
    """Keyword events overlapping today..today+days, one per (start, title).

    Matching (and dedupe) use the raw title, a case-insensitive substring as for
    the v1 highlights ticker; the entry shows its closed-label title.
    Spans are returned whole; the page collapses them to "Nov 26–27".
    """
    start, end = today.isoformat(), (today + timedelta(days=days)).isoformat()
    lowered = [k.lower() for k in keywords]

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for e in events:
        if e["end_date"] < start or e["start_date"] > end:
            continue
        title_low = e["title"].lower()
        if not any(k in title_low for k in lowered):
            continue
        key = (e["start_date"], e["title"])
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "start_date": e["start_date"],
                "end_date": e["end_date"],
                "title": closed_title(e, closed_labels, holiday_categories),
                "category": e["category"],
            }
        )
    return items[:RADAR_MAX]


# --- Waste strip -----------------------------------------------------------


def _pickups(events: list[Event], today: date) -> list[dict[str, Any]]:
    """Pickup days from today on, one per date, items merged in title order.

    A pickup is any event whose title carries a TRASH_REMINDER_KEYWORDS term,
    whatever feed it came from — the same rule the trash alert uses.
    """
    by_date: dict[str, list[str]] = {}
    for e in events:
        if e["start_date"] < today.isoformat() or not matches_trash(e["title"]):
            continue
        items = by_date.setdefault(e["start_date"], [])
        items.extend(p.strip() for p in e["title"].split(" · ") if p.strip())

    pickups: list[dict[str, Any]] = []
    for when in sorted(by_date):
        items = list(dict.fromkeys(by_date[when]))  # dedupe, keep order
        pickups.append({"date": when, "title": " · ".join(items), "items": items})
    return pickups


def _kind(title: str, recycle: tuple[str, ...], bulky: tuple[str, ...]) -> str:
    # Recycling takes precedence (the household's rule). In this feed bulky
    # normally shares the recycling day, so "bulky" only shows for a pickup
    # that lists bulky without recycling.
    low = title.lower()
    if any(k.lower() in low for k in recycle):
        return "recycle"
    if any(k.lower() in low for k in bulky):
        return "bulky"
    return "regular"


def waste(
    events: list[Event],
    today: date,
    recycle_keywords: tuple[str, ...] = WASTE_RECYCLE_KEYWORDS,
    bulky_keywords: tuple[str, ...] = WASTE_BULKY_KEYWORDS,
) -> dict[str, Any]:
    """The next two pickups and the strip colour (``week_kind``).

    The colour follows the first not-yet-passed pickup in the Sun–Sat week
    containing today, or, once those have passed, the first pickup after this
    week. Pickups are sorted from today on, so either way that is simply the
    first upcoming pickup; a later pickup in the same week does not change the
    colour. A pickup listing both recycling and bulky is "recycle".
    """
    pickups = _pickups(events, today)
    nxt, following = _first(pickups, 2)
    kind = _kind(nxt["title"], recycle_keywords, bulky_keywords) if nxt else "regular"
    return {"next": nxt, "following": following, "week_kind": kind}
