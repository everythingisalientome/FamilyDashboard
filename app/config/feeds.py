"""Calendar feeds (``CAL_<KEY>_*``) and the calendar refresh schedule."""

import os
import re
from dataclasses import dataclass, replace

from app.config.env import _env_int, _env_str

# --- Calendars -------------------------------------------------------------


@dataclass(frozen=True)
class CalendarFeed:
    """One ICS source. ``key`` is the stable id stored on every event row."""

    key: str
    label: str
    url: str
    color: str
    #: If set (via ``CAL_<KEY>_ALERT_COLOR``), any event from this feed covering
    #: today raises an alert in the photo-panel overlay in this colour. Blank =
    #: this feed never alerts — it just shows on the calendar as usual.
    alert_color: str = ""


#: Every ICS feed — the family Google Calendar included — is a capability URL
#: (anyone holding it can read the calendar), so all of them live in ``.env``,
#: never here. A feed is defined entirely by environment variables:
#:
#:     CAL_<KEY>_URL      the ICS URL (required — its presence defines the feed)
#:     CAL_<KEY>_LABEL    legend label   (optional; defaults to <Key>)
#:     CAL_<KEY>_COLOR    chip colour    (optional; defaults from the palette)
#:     CAL_<KEY>_ORDER    sort position  (optional integer; defaults to 100)
#:
#: Nothing enumerates the feeds — they are discovered by scanning the
#: environment, so adding another calendar tomorrow is just three new lines in
#: ``.env`` and a restart. See ``.env.example`` for the full set.
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
        label = os.getenv(f"CAL_{raw_key}_LABEL", "").strip() or key.title()
        color = os.getenv(f"CAL_{raw_key}_COLOR", "").strip()
        alert_color = os.getenv(f"CAL_{raw_key}_ALERT_COLOR", "").strip()
        order_raw = os.getenv(f"CAL_{raw_key}_ORDER", "").strip()
        order = int(order_raw) if order_raw.lstrip("-").isdigit() else 100
        discovered.append(
            (order, key, CalendarFeed(key, label, url, color, alert_color))
        )

    # Back-compat: the original single-feed variable still works if present.
    legacy = os.getenv("FAMILY_CALENDAR_ICS_URL", "").strip()
    if legacy and not any(key == "family" for _, key, _ in discovered):
        discovered.append(
            (0, "family", CalendarFeed("family", "Family", legacy, ""))
        )

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

#: How far ahead events are expanded and stored.
EVENT_HORIZON_DAYS: int = 30
