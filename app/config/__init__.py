"""Central configuration. Feed URLs, intervals, and paths live here.

Split by topic into submodules; this package re-exports every public name so
``from app.config import X`` and ``config.X`` keep working unchanged. ``env``
is imported first: it loads ``.env`` before any other module reads a setting.
"""

from app.config.env import (
    BASE_DIR,
    DATA_DIR,
    DB_PATH,
    LOG_DIR,
    LOG_FILE_NAME,
    LOG_LEVEL,
    LOG_RETENTION_DAYS,
    PHOTOS_DIR,
    STATIC_DIR,
)
from app.config.feeds import (
    CALENDAR_FEEDS,
    CALENDAR_REFRESH_DAY,
    CALENDAR_REFRESH_HOUR,
    CALENDAR_REFRESH_MINUTE,
    CalendarFeed,
    EVENT_CACHE_DAYS,
    EVENT_HORIZON_DAYS,
    GCAL_CALENDAR_ID,
    GCAL_FEED_KEY,
    GCAL_SCOPES,
    GCAL_SERVICE_ACCOUNT_FILE,
    RETIRED_FAMILY_VARS,
)
from app.config.persons import (
    FAMILY_FEEDS,
    PERSONS,
    PERSON_COLOR_FEEDS,
    Person,
)
from app.config.weather import (
    FORECAST_DAYS,
    NWS_USER_AGENT,
    WEATHER_LAT,
    WEATHER_LON,
    WEATHER_REFRESH_SECONDS,
)
from app.config.alerts import (
    ALERTS_REFRESH_SECONDS,
    ALERT_CYCLE_SECONDS,
    ALERT_RED_SEVERITIES,
    ALERT_ROTATE_SECONDS,
    ALERT_SAFETY_SEVERITIES,
    ALERT_SHOW_SECONDS,
    ALERT_WEATHER_KEYWORDS,
    CLOSURE_ALERT_CATEGORIES,
    TRASH_REMINDER_HOUR,
    TRASH_REMINDER_KEYWORDS,
)
from app.config.display import (
    DATA_REFRESH_SECONDS,
    DISPLAY_TZ,
    DISPLAY_TZ_NAME,
    EVENT_EXCLUDE_KEYWORDS,
    FETCH_TIMEOUT_SECONDS,
    HERO_HOLIDAY_CATEGORIES,
    HIGHLIGHT_DAYS,
    HIGHLIGHT_KEYWORDS,
    IMPORT_DAYCARE_PERSONS,
    NIGHT_MODE_START,
    NIGHTLY_RELOAD_HOUR,
    PHOTOS_ALBUM_URL,
    PHOTO_EXTENSIONS,
    PHOTO_INTERVAL_SECONDS,
    PHOTO_LIST_REFRESH_SECONDS,
    PHOTO_SYNC_HEIGHT,
    PHOTO_SYNC_MAX,
    PHOTO_SYNC_PREFIX,
    PHOTO_SYNC_REFRESH_SECONDS,
    PHOTO_SYNC_WIDTH,
    RADAR_DAYS,
    RADAR_KEYWORDS,
    WASTE_BULKY_KEYWORDS,
    WASTE_RECYCLE_KEYWORDS,
)

__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "DB_PATH",
    "LOG_DIR",
    "LOG_FILE_NAME",
    "LOG_LEVEL",
    "LOG_RETENTION_DAYS",
    "PHOTOS_DIR",
    "STATIC_DIR",
    "CALENDAR_FEEDS",
    "CALENDAR_REFRESH_DAY",
    "CALENDAR_REFRESH_HOUR",
    "CALENDAR_REFRESH_MINUTE",
    "CalendarFeed",
    "EVENT_CACHE_DAYS",
    "EVENT_HORIZON_DAYS",
    "GCAL_CALENDAR_ID",
    "GCAL_FEED_KEY",
    "GCAL_SCOPES",
    "GCAL_SERVICE_ACCOUNT_FILE",
    "RETIRED_FAMILY_VARS",
    "FAMILY_FEEDS",
    "PERSONS",
    "PERSON_COLOR_FEEDS",
    "Person",
    "FORECAST_DAYS",
    "NWS_USER_AGENT",
    "WEATHER_LAT",
    "WEATHER_LON",
    "WEATHER_REFRESH_SECONDS",
    "ALERTS_REFRESH_SECONDS",
    "ALERT_CYCLE_SECONDS",
    "ALERT_RED_SEVERITIES",
    "ALERT_ROTATE_SECONDS",
    "ALERT_SAFETY_SEVERITIES",
    "ALERT_SHOW_SECONDS",
    "ALERT_WEATHER_KEYWORDS",
    "CLOSURE_ALERT_CATEGORIES",
    "TRASH_REMINDER_HOUR",
    "TRASH_REMINDER_KEYWORDS",
    "DATA_REFRESH_SECONDS",
    "DISPLAY_TZ",
    "DISPLAY_TZ_NAME",
    "EVENT_EXCLUDE_KEYWORDS",
    "FETCH_TIMEOUT_SECONDS",
    "HERO_HOLIDAY_CATEGORIES",
    "HIGHLIGHT_DAYS",
    "HIGHLIGHT_KEYWORDS",
    "IMPORT_DAYCARE_PERSONS",
    "NIGHT_MODE_START",
    "NIGHTLY_RELOAD_HOUR",
    "PHOTOS_ALBUM_URL",
    "PHOTO_EXTENSIONS",
    "PHOTO_INTERVAL_SECONDS",
    "PHOTO_LIST_REFRESH_SECONDS",
    "PHOTO_SYNC_HEIGHT",
    "PHOTO_SYNC_MAX",
    "PHOTO_SYNC_PREFIX",
    "PHOTO_SYNC_REFRESH_SECONDS",
    "PHOTO_SYNC_WIDTH",
    "RADAR_DAYS",
    "RADAR_KEYWORDS",
    "WASTE_BULKY_KEYWORDS",
    "WASTE_RECYCLE_KEYWORDS",
]

# The admin dry-run imports this package in strict mode to vet a candidate
# .env before saving it; a normal boot never runs these checks.
from app.config.env import STRICT as _STRICT  # noqa: E402

if _STRICT:
    from app.config.strict import check as _strict_check

    _strict_check()
