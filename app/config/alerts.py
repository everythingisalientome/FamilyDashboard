"""Alert pill timing and the rules for what raises an alert."""

from app.config.env import _env_int, _env_str

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
    for c in _env_str("CLOSURE_ALERT_CATEGORIES", "school, holiday, dismissal").split(",")
    if c.strip()
)
