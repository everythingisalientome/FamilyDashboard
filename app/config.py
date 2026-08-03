"""Central configuration. Feed URLs, intervals, and paths live here."""

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# --- Env helpers -----------------------------------------------------------
# Every tunable is read from the environment with the old hardcoded value as
# the fallback, so config.py stays the single place that names each setting
# while .env is where they are actually changed. A blank or unparseable value
# falls back to the default rather than crashing the process on boot.


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


# --- Paths -----------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent
STATIC_DIR: Path = BASE_DIR / "static"
PHOTOS_DIR: Path = BASE_DIR / "photos"
DATA_DIR: Path = BASE_DIR / "data"
DB_PATH: Path = DATA_DIR / "dashboard.db"

# --- Logging ---------------------------------------------------------------
# The app writes its own rotating log so the startup/fetch/admin lines are
# captured no matter how it is launched (dev server or NSSM service) and can be
# shown on the admin page. This is separate from NSSM's stdout capture.

#: Directory the log files live in. Defaults under data/ (git-ignored). Override
#: with an absolute path in .env to send logs elsewhere.
_LOG_DIR_RAW = _env_str("LOG_DIR", "")
LOG_DIR: Path = Path(_LOG_DIR_RAW) if _LOG_DIR_RAW else DATA_DIR / "logs"

#: Base name of the active log file. Rotated files get a ``.YYYY-MM-DD`` suffix.
LOG_FILE_NAME: str = "dashboard.log"

#: Root log level (DEBUG/INFO/WARNING/ERROR). Anything unrecognised → INFO.
LOG_LEVEL: str = _env_str("LOG_LEVEL", "INFO").upper()

#: How many past daily files to keep. The active file rolls at local midnight;
#: files older than this many days are pruned automatically.
LOG_RETENTION_DAYS: int = _env_int("LOG_RETENTION_DAYS", 14)

# --- Display ---------------------------------------------------------------

DISPLAY_TZ_NAME: str = "America/New_York"
DISPLAY_TZ: ZoneInfo = ZoneInfo(DISPLAY_TZ_NAME)

#: Hour (local) at which the browser reloads itself to shed leaks / stale JS.
NIGHTLY_RELOAD_HOUR: int = 3

# --- Photos ----------------------------------------------------------------

#: Seconds each photo stays on screen before crossfading to the next.
PHOTO_INTERVAL_SECONDS: int = _env_int("PHOTO_INTERVAL_SECONDS", 10)

#: How often the page re-reads the photo list so new drops appear on their own.
PHOTO_LIST_REFRESH_SECONDS: int = _env_int("PHOTO_LIST_REFRESH_SECONDS", 30 * 60)

PHOTO_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
)

# --- Photos: Google Photos sync --------------------------------------------

#: A Google Photos *public* shared-album link ("anyone with the link can
#: view"). A background job scrapes this page — no Google login — downloads
#: each image into PHOTOS_DIR, and the existing slideshow shows them in order.
#: Blank disables the sync entirely; manual drops into photos/ still work.
PHOTOS_ALBUM_URL: str = _env_str("PHOTOS_ALBUM_URL", "")

#: How often the album is re-synced (default hourly). New photos added to the
#: album on your phone appear on the wall within this window, no restart needed.
PHOTO_SYNC_REFRESH_SECONDS: int = _env_int("PHOTO_SYNC_REFRESH_SECONDS", 60 * 60)

#: Cap on how many album photos to keep locally (0 = no cap). Newest-first.
PHOTO_SYNC_MAX: int = _env_int("PHOTO_SYNC_MAX", 300)

#: Pixel box each photo is downloaded at — fit within, never cropped.
PHOTO_SYNC_WIDTH: int = _env_int("PHOTO_SYNC_WIDTH", 1920)
PHOTO_SYNC_HEIGHT: int = _env_int("PHOTO_SYNC_HEIGHT", 1080)

#: Filename prefix on every synced file, so the sync only ever prunes its own
#: downloads — a photo you dropped into photos/ by hand is never touched.
PHOTO_SYNC_PREFIX: str = "gphoto_"

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

# --- Weather ---------------------------------------------------------------

#: Harrisburg, NC by default. NWS resolves this to grid GSP/125,70. Override
#: WEATHER_LAT/WEATHER_LON in .env to point the dashboard somewhere else.
WEATHER_LAT: float = _env_float("WEATHER_LAT", 35.3238)
WEATHER_LON: float = _env_float("WEATHER_LON", -80.6581)

#: api.weather.gov asks for a contact address in the User-Agent.
NWS_USER_AGENT: str = _env_str(
    "NWS_USER_AGENT", "(FamilyWallDashboard, preetpnd@gmail.com)"
)

WEATHER_REFRESH_SECONDS: int = _env_int("WEATHER_REFRESH_SECONDS", 30 * 60)

#: Days shown in the outlook strip, not counting today.
FORECAST_DAYS: int = _env_int("FORECAST_DAYS", 4)

# --- Highlights ticker -----------------------------------------------------

#: A one-line, non-scrolling strip of upcoming items shown between the agenda
#: and weather. Any event in the next HIGHLIGHT_DAYS whose title contains one of
#: these keywords (case-insensitive) is listed. Empty disables the strip.
HIGHLIGHT_KEYWORDS: tuple[str, ...] = tuple(
    k.strip() for k in _env_str("HIGHLIGHT_KEYWORDS", "").split(",") if k.strip()
)

#: How far ahead the ticker looks.
HIGHLIGHT_DAYS: int = _env_int("HIGHLIGHT_DAYS", 7)

# --- Alerts ----------------------------------------------------------------
# Alerts surface as a single shiny pill at the bottom of the photo panel that
# rotates through the active alerts one at a time — they never push the dashboard
# layout. Two halves: NWS active weather alerts are *fetched* (fetchers/alerts.py,
# cached); closures, trash and per-calendar alerts are *derived* at request time
# in /api/alerts from data already cached, so they need no fetch and no table.

#: How often the server polls NWS for active alerts covering WEATHER_LAT/LON.
ALERTS_REFRESH_SECONDS: int = _env_int("ALERTS_REFRESH_SECONDS", 10 * 60)

#: The overlay stays hidden, then fades in for ALERT_SHOW_SECONDS once every
#: ALERT_CYCLE_SECONDS — by default 1 minute in view every 30 minutes. Within a
#: window alerts show one at a time (not stacked), each on screen for
#: ALERT_ROTATE_SECONDS before crossfading to the next. Sent to the frontend via
#: /api/settings so the page owns the show/rotate clock.
ALERT_SHOW_SECONDS: int = _env_int("ALERT_SHOW_SECONDS", 60)
ALERT_CYCLE_SECONDS: int = _env_int("ALERT_CYCLE_SECONDS", 30 * 60)
ALERT_ROTATE_SECONDS: int = _env_int("ALERT_ROTATE_SECONDS", 7)

#: NWS event-name substrings that always qualify as an alert (case-insensitive),
#: e.g. "Severe Thunderstorm Warning" and "Heat Advisory".
ALERT_WEATHER_KEYWORDS: tuple[str, ...] = tuple(
    k.strip()
    for k in _env_str(
        "ALERT_WEATHER_KEYWORDS", "thunderstorm, lightning, heat advisory"
    ).split(",")
    if k.strip()
)

#: Safety net: any NWS alert at one of these severities qualifies too, even if
#: its event name is not in the keyword list — so a Tornado / Flash Flood
#: Warning is never silently dropped. Blank disables the net (keyword-only).
ALERT_SAFETY_SEVERITIES: frozenset[str] = frozenset(
    s.strip().title()
    for s in _env_str("ALERT_SAFETY_SEVERITIES", "Extreme,Severe").split(",")
    if s.strip()
)

#: A qualifying NWS alert is shiny red when it is a warning (severity in this
#: set, or "warning" in its event name) and shiny gold-orange otherwise
#: (advisories / watches, e.g. a Heat Advisory). Closures are always red; trash
#: is always gold. The two tones are styled in the frontend (alerts.css); a
#: calendar can override with its own colour via CAL_<KEY>_ALERT_COLOR.
ALERT_RED_SEVERITIES: frozenset[str] = frozenset(
    s.strip().title()
    for s in _env_str("ALERT_RED_SEVERITIES", "Extreme,Severe").split(",")
    if s.strip()
)

#: Event-title keywords that mark a trash/recycling pickup (always gold). A
#: pickup today, or tomorrow once it is past TRASH_REMINDER_HOUR, raises it.
TRASH_REMINDER_KEYWORDS: tuple[str, ...] = tuple(
    k.strip()
    for k in _env_str(
        "TRASH_REMINDER_KEYWORDS", "trash, recycling, garbage, yard waste"
    ).split(",")
    if k.strip()
)

#: Local hour (24h) from which "trash tomorrow" starts showing the evening
#: before. Before this, tomorrow's pickup is not yet nagging.
TRASH_REMINDER_HOUR: int = _env_int("TRASH_REMINDER_HOUR", 17)

#: Which event_styles categories count as a school closure / early dismissal
#: (always red) when one covers today on a weekday. Reuses the Phase 2 keyword
#: matcher — no second keyword list.
CLOSURE_ALERT_CATEGORIES: frozenset[str] = frozenset(
    c.strip().lower()
    for c in _env_str("CLOSURE_ALERT_CATEGORIES", "school, holiday").split(",")
    if c.strip()
)

# --- Frontend polling ------------------------------------------------------

#: How often the page re-reads /api/events and /api/weather. Both serve cached
#: rows, so this is cheap and unrelated to how often the fetchers run.
DATA_REFRESH_SECONDS: int = _env_int("DATA_REFRESH_SECONDS", 5 * 60)

#: Timeout for every outbound fetch.
FETCH_TIMEOUT_SECONDS: float = _env_float("FETCH_TIMEOUT_SECONDS", 30.0)
