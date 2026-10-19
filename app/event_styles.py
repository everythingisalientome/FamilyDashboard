"""Keyword-based event categories that colour an event beyond its calendar.

An event whose title matches a category's keywords (word-boundary, case
-insensitive) is drawn in that category's colour on the month grid and agenda
instead of its feed's colour, and its day cells are tinted — so a multi-day
span (a whole break week) reads as one continuous block.

Three categories ship by default; every one is tunable in ``.env``, and new
ones can be declared there:

    EVENT_STYLE_<KEY>_KEYWORDS = extra, phrases   (appended to the built-ins)
    EVENT_STYLE_<KEY>_COLOR    = #rrggbb          (overrides the built-in)
    EVENT_STYLE_<KEY>_ORDER    = <int>            (lower wins when >1 matches)

A brand-new <KEY> (one with no built-in) needs at least KEYWORDS and COLOR to
become usable. Location-specific terms — Cabarrus's "Capped/Uncapped Workday",
say — belong in ``.env`` rather than here.
"""

import os
import re
from dataclasses import dataclass

#: key -> (order, colour, built-in keywords). Lower order wins on overlap.
_DEFAULTS: dict[str, tuple[int, str, tuple[str, ...]]] = {
    "quarter": (
        10,
        "#b197fc",  # purple
        ("end of quarter", "quarter ends", "end of grading period",
         "grading period ends"),
    ),
    "school": (
        20,
        "#ffab00",  # golden-orange
        ("first day of school", "last day of school", "early dismissal",
         "early release", "closes"),  # "Closes 12:00 – …" (importer early_close)
    ),
    "holiday": (
        30,
        "#ff6b6b",  # red
        ("holiday", "no school", "no classes", "day off", "teacher workday",
         "workday", "recess", "break", "closed", "closure", "vacation",
         "christmas", "thanksgiving", "new year", "independence day",
         "fourth of july", "july 4", "memorial day", "labor day",
         "veterans day", "columbus day", "juneteenth", "martin luther king",
         "mlk", "presidents day", "president's day", "easter", "good friday",
         "halloween"),
    ),
}


@dataclass(frozen=True)
class EventCategory:
    key: str
    color: str
    order: int
    pattern: re.Pattern

    def matches(self, title: str | None) -> bool:
        return bool(self.pattern.search(title or ""))


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def compile_keywords(keywords: tuple[str, ...]) -> re.Pattern:
    # Trailing "s?" so a singular keyword still matches the plural title the
    # calendar actually uses ("workday" -> "Capped Workdays"). The word boundary
    # still keeps "break" out of "Breakfast".
    alternation = "|".join(re.escape(k) for k in keywords)
    return re.compile(rf"\b(?:{alternation})s?\b", re.IGNORECASE)


def _load() -> tuple[EventCategory, ...]:
    # Start with the built-ins, then let the environment declare extra keys.
    keys = set(_DEFAULTS)
    for name in os.environ:
        found = re.match(r"^EVENT_STYLE_(.+)_KEYWORDS$", name)
        if found:
            keys.add(found.group(1).lower())

    categories: list[EventCategory] = []
    for key in keys:
        order, color, keywords = _DEFAULTS.get(key, (100, "", ()))
        env = key.upper()

        extra = os.getenv(f"EVENT_STYLE_{env}_KEYWORDS", "")
        if extra:
            keywords = keywords + _csv(extra)
        color = os.getenv(f"EVENT_STYLE_{env}_COLOR", "").strip() or color
        raw_order = os.getenv(f"EVENT_STYLE_{env}_ORDER", "").strip()
        if raw_order.lstrip("-").isdigit():
            order = int(raw_order)

        if keywords and color:  # a category needs both to be usable
            categories.append(EventCategory(key, color, order, compile_keywords(keywords)))

    categories.sort(key=lambda c: (c.order, c.key))
    return tuple(categories)


EVENT_CATEGORIES: tuple[EventCategory, ...] = _load()


def categorize(title: str | None) -> EventCategory | None:
    """The highest-precedence category whose keywords match, or None."""
    for category in EVENT_CATEGORIES:
        if category.matches(title):
            return category
    return None
