"""Weather location, NWS contact and forecast tunables."""

from app.config.env import _env_float, _env_int, _env_str

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
