"""What the page shows and how often: display timezone, photos, the v1
highlights ticker, the v2 hero/radar/waste tunables and polling/timeouts."""

from zoneinfo import ZoneInfo

from app.config.env import _env_csv, _env_float, _env_int, _env_str

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

# --- Highlights ticker -----------------------------------------------------

#: A one-line, non-scrolling strip of upcoming items shown between the agenda
#: and weather. Any event in the next HIGHLIGHT_DAYS whose title contains one of
#: these keywords (case-insensitive) is listed. Empty disables the strip.
HIGHLIGHT_KEYWORDS: tuple[str, ...] = tuple(
    k.strip() for k in _env_str("HIGHLIGHT_KEYWORDS", "").split(",") if k.strip()
)

#: How far ahead the ticker looks.
HIGHLIGHT_DAYS: int = _env_int("HIGHLIGHT_DAYS", 7)

# --- v2 wall: hero, radar, waste ------------------------------------------

#: event_styles categories that count as a "NEXT HOLIDAY" in the hero.
HERO_HOLIDAY_CATEGORIES: frozenset[str] = frozenset(
    k.lower() for k in _env_csv("HERO_HOLIDAY_CATEGORIES", "holiday")
)

#: The "On the radar" footer: events in the next RADAR_DAYS whose title
#: contains one of these (case-insensitive). The v1 ticker's HIGHLIGHT_* stays.
RADAR_KEYWORDS: tuple[str, ...] = _env_csv(
    "RADAR_KEYWORDS",
    "first day of school, early dismissal, no school, holiday, end of quarter, "
    "capped workday",
)
RADAR_DAYS: int = _env_int("RADAR_DAYS", 30)

#: Waste strip colour: the week's deciding pickup (TRASH_REMINDER_KEYWORDS)
#: is "recycle" if its title has one of these, else "bulky", else "regular".
WASTE_RECYCLE_KEYWORDS: tuple[str, ...] = _env_csv(
    "WASTE_RECYCLE_KEYWORDS", "recycling"
)
WASTE_BULKY_KEYWORDS: tuple[str, ...] = _env_csv("WASTE_BULKY_KEYWORDS", "bulky")

# --- Frontend polling ------------------------------------------------------

#: How often the page re-reads /api/events and /api/weather. Both serve cached
#: rows, so this is cheap and unrelated to how often the fetchers run.
DATA_REFRESH_SECONDS: int = _env_int("DATA_REFRESH_SECONDS", 5 * 60)

#: Timeout for every outbound fetch.
FETCH_TIMEOUT_SECONDS: float = _env_float("FETCH_TIMEOUT_SECONDS", 30.0)
