"""Map NWS icon URLs onto the small set of glyphs the page draws itself.

The display must never reach out to api.weather.gov for images, so the URL is
reduced to a key like ``clear-night`` and the SVG lives in static/.
"""

import re

#: NWS condition tokens -> our glyph names. Anything unlisted falls back to
#: the daylight-appropriate clear icon.
_CONDITIONS: dict[str, str] = {
    "skc": "clear",
    "few": "clear",
    "sct": "partly",
    "bkn": "partly",
    "ovc": "cloudy",
    "wind_skc": "wind",
    "wind_few": "wind",
    "wind_sct": "wind",
    "wind_bkn": "wind",
    "wind_ovc": "wind",
    "rain": "rain",
    "rain_showers": "rain",
    "rain_showers_hi": "rain",
    "tsra": "thunder",
    "tsra_sct": "thunder",
    "tsra_hi": "thunder",
    "snow": "snow",
    "blizzard": "snow",
    "cold": "snow",
    "rain_snow": "sleet",
    "rain_sleet": "sleet",
    "snow_sleet": "sleet",
    "sleet": "sleet",
    "fzra": "sleet",
    "rain_fzra": "sleet",
    "snow_fzra": "sleet",
    "fog": "fog",
    "haze": "fog",
    "smoke": "fog",
    "dust": "fog",
    "hot": "hot",
    "hurricane": "wind",
    "tropical_storm": "wind",
    "tornado": "wind",
}

#: Glyphs that look different after dark.
_NIGHT_VARIANTS = frozenset({"clear", "partly"})

_ICON_PATH = re.compile(r"/icons/[^/]+/(day|night)/([a-z_]+)")


def icon_key(icon_url: str | None, is_daytime: bool | None = None) -> str | None:
    """``.../icons/land/night/tsra,60?size=medium`` -> ``thunder``.

    Returns ``None`` when there is no URL to read, letting the caller fall back
    to another source rather than inventing a condition.
    """
    if not icon_url:
        return None

    match = _ICON_PATH.search(icon_url)
    if not match:
        return None

    period, token = match.groups()
    night = (period == "night") if is_daytime is None else not is_daytime
    name = _CONDITIONS.get(token, "clear")

    if name in _NIGHT_VARIANTS and night:
        return f"{name}-night"
    return name
