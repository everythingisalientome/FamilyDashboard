"""Calendar feeds (``CAL_<KEY>_*``) and the calendar refresh schedule."""

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from app.config.env import BASE_DIR, _env_int, _env_str

# --- Calendars -------------------------------------------------------------


@dataclass(frozen=True)
class CalendarFeed:
    """One calendar source. ``key`` is the stable id stored on every event row.

    ``url`` is the ICS URL; blank for the Google-API family feed.
    """

    key: str
    label: str
    url: str
    color: str
    #: If set (via ``CAL_<KEY>_ALERT_COLOR``), any event from this feed covering
    #: today raises an alert in the photo-panel overlay in this colour. Blank =
    #: this feed never alerts — it just shows on the calendar as usual.
    alert_color: str = ""
    #: If set (via ``CAL_<KEY>_CLOSED_LABEL``), holiday-category events from this
    #: feed read "<label> – <title before its first ':'>" on the hero's NEXT
    #: HOLIDAY line and the radar. Grid chips keep the raw title.
    closed_label: str = ""
    #: The same for early-dismissal events (``CAL_<KEY>_DISMISSAL_LABEL``); the
    #: label text already in the title is dropped (app/event_labels.py).
    dismissal_label: str = ""


#: Every ICS feed is a capability URL (anyone holding it can read the
#: calendar), so all of them live in ``.env``, never here. A feed is defined
#: entirely by environment variables:
#:
#:     CAL_<KEY>_URL      the ICS URL (required — its presence defines the feed)
#:     CAL_<KEY>_LABEL    legend label   (optional; defaults to <Key>)
#:     CAL_<KEY>_COLOR    chip colour    (optional; defaults from the palette)
#:     CAL_<KEY>_ORDER    sort position  (optional integer; defaults to 100)
#:
#: Nothing enumerates the feeds — they are discovered by scanning the
#: environment, so adding another calendar tomorrow is just three new lines in
#: ``.env`` and a restart. See ``.env.example`` for the full set.
#:
#: The one exception is ``family``: it is read through the Google Calendar API
#: (app/fetchers/gcal.py), not ICS, and exists when ``GCAL_CALENDAR_ID`` is set.
#: It keeps its ``CAL_FAMILY_LABEL/_COLOR/_ORDER/_ALERT_COLOR`` settings and has
#: ``url=""`` so the ICS fetcher skips it.
_FEED_URL_RE = re.compile(r"^CAL_(.+)_URL$")

#: Chip colours handed out, in order, to feeds that don't name their own.
_FEED_PALETTE: tuple[str, ...] = (
    "#ffa94d",  # orange
    "#74c0fc",  # blue
    "#51cf66",  # green
    "#f783ac",  # pink
    "#a78bfa",  # violet
    "#ffd43b",  # amber
)

# --- Google Calendar (the family feed) -------------------------------------

#: Explicit calendar id from Google Calendar -> Settings -> Integrate calendar
#: (never ``primary``: for a service account that is its own empty calendar).
#: Blank = the family feed is disabled.
GCAL_CALENDAR_ID: str = _env_str("GCAL_CALENDAR_ID", "")

#: Service-account JSON key; a relative path resolves against the repo root.
_GCAL_SA_RAW = Path(_env_str("GCAL_SERVICE_ACCOUNT_FILE", "data/gcal-sa.json"))
GCAL_SERVICE_ACCOUNT_FILE: Path = (
    _GCAL_SA_RAW if _GCAL_SA_RAW.is_absolute() else BASE_DIR / _GCAL_SA_RAW
)

#: One scope for reading today and writing (the Phase 4 importer) later.
GCAL_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/calendar.events",)

#: The feed key the Google calendar is stored under (colours, order, fetch_meta).
GCAL_FEED_KEY = "family"

#: Retired ICS variables for the family calendar, still set in ``.env``. Logged
#: as ignored at startup (logging isn't configured yet at import time).
RETIRED_FAMILY_VARS: tuple[str, ...] = tuple(
    name
    for name in ("CAL_FAMILY_URL", "FAMILY_CALENDAR_ICS_URL")
    if os.getenv(name, "").strip()
)


def _feed_entry(raw_key: str, key: str, url: str) -> tuple[int, str, CalendarFeed]:
    """(order, key, feed) from the optional ``CAL_<KEY>_*`` display settings."""
    label = os.getenv(f"CAL_{raw_key}_LABEL", "").strip() or key.title()
    color = os.getenv(f"CAL_{raw_key}_COLOR", "").strip()
    alert_color = os.getenv(f"CAL_{raw_key}_ALERT_COLOR", "").strip()
    closed_label = os.getenv(f"CAL_{raw_key}_CLOSED_LABEL", "").strip()
    dismissal = os.getenv(f"CAL_{raw_key}_DISMISSAL_LABEL", "").strip()
    order_raw = os.getenv(f"CAL_{raw_key}_ORDER", "").strip()
    order = int(order_raw) if order_raw.lstrip("-").isdigit() else 100
    return order, key, CalendarFeed(
        key, label, url, color, alert_color, closed_label, dismissal
    )


def _load_calendar_feeds() -> tuple[CalendarFeed, ...]:
    """Build the feed list from ``CAL_<KEY>_*`` environment variables."""
    discovered: list[tuple[int, str, CalendarFeed]] = []
    for env_name, value in os.environ.items():
        match = _FEED_URL_RE.match(env_name)
        if not match:
            continue
        url = value.strip()
        if not url:  # declared but blank — skip, same as absent
            continue
        raw_key = match.group(1)
        key = raw_key.lower()
        if key == GCAL_FEED_KEY:  # retired: the family feed is the Google API
            continue
        discovered.append(_feed_entry(raw_key, key, url))

    if GCAL_CALENDAR_ID:
        discovered.append(_feed_entry("FAMILY", GCAL_FEED_KEY, ""))

    discovered.sort(key=lambda item: (item[0], item[1]))

    # Hand out palette colours to feeds that named none, skipping any colour
    # already claimed so a bare new feed still reads as its own calendar.
    used = {feed.color.lower() for _, _, feed in discovered if feed.color}
    spare = (c for c in _FEED_PALETTE if c.lower() not in used)

    feeds: list[CalendarFeed] = []
    for _, _, feed in discovered:
        color = feed.color or next(spare, _FEED_PALETTE[len(feeds) % len(_FEED_PALETTE)])
        feeds.append(replace(feed, color=color))
    return tuple(feeds)


#: Discovered feeds, ordered for display/legend. Empty if none are configured.
CALENDAR_FEEDS: tuple[CalendarFeed, ...] = _load_calendar_feeds()

#: Calendars change rarely, so they refresh on a nightly wall-clock schedule
#: (default every day at 23:00 local) rather than a short interval. A restart
#: still fetches immediately (see scheduler.py), so a newly added feed shows up
#: without waiting for the next run. Day is an APScheduler ``day_of_week``:
#: ``*`` for every day, or a name (mon..sun) / 0-6 (mon=0) to pin it to one day
#: (e.g. ``sat`` for weekly). Hour/minute are 24-hour local time.
CALENDAR_REFRESH_DAY: str = _env_str("CALENDAR_REFRESH_DAY", "*")
CALENDAR_REFRESH_HOUR: int = _env_int("CALENDAR_REFRESH_HOUR", 23)
CALENDAR_REFRESH_MINUTE: int = _env_int("CALENDAR_REFRESH_MINUTE", 0)

#: How far ahead /api/events lists events (the grid / v1 agenda window).
EVENT_HORIZON_DAYS: int = 30

#: How far ahead the calendar fetchers expand and store events. Longer than the
#: list window so the hero's NEXT UP / NEXT HOLIDAY can see a closure weeks out.
EVENT_CACHE_DAYS: int = max(_env_int("EVENT_CACHE_DAYS", 90), EVENT_HORIZON_DAYS)
