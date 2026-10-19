"""Household members (``PERSON_<KEY>_*``) for the v2 wall."""

import os
import re
from dataclasses import dataclass, replace

from app.config.env import _env_csv
from app.config.feeds import _FEED_PALETTE, CALENDAR_FEEDS

# --- Persons (v2 wall) -----------------------------------------------------


@dataclass(frozen=True)
class Person:
    """One household member with a column on the v2 wall.

    An event belongs to a person when its DB ``person`` tag names them (set by
    the Google feed, Phase 4), else when it comes from one of their ``feeds``
    or its title matches one of their ``keywords`` — see app/persons.py.
    """

    key: str
    label: str
    color: str
    order: int
    feeds: tuple[str, ...]
    keywords: tuple[str, ...]


#: Persons are discovered like feeds, by scanning for the anchor variable:
#:
#:     PERSON_<KEY>_LABEL     display name (required — defines the person)
#:     PERSON_<KEY>_COLOR     #rrggbb   (optional; defaults from the palette)
#:     PERSON_<KEY>_ORDER     int, lower first (the hero shows the first two)
#:     PERSON_<KEY>_FEEDS     comma list of feed keys wholly theirs (school)
#:     PERSON_<KEY>_KEYWORDS  comma list, word-boundary title match (prisha)
_PERSON_LABEL_RE = re.compile(r"^PERSON_(.+)_LABEL$")


def _person_csv(raw_key: str, suffix: str) -> tuple[str, ...]:
    """A PERSON_<KEY>_<SUFFIX> comma list; blank is a legitimate empty list."""
    raw = os.getenv(f"PERSON_{raw_key}_{suffix}", "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _load_persons() -> tuple[Person, ...]:
    """Build the person list from ``PERSON_<KEY>_*`` environment variables."""
    found: list[Person] = []
    for env_name, value in os.environ.items():
        match = _PERSON_LABEL_RE.match(env_name)
        if not match or not value.strip():
            continue
        raw_key = match.group(1)
        order_raw = os.getenv(f"PERSON_{raw_key}_ORDER", "").strip()
        found.append(
            Person(
                key=raw_key.lower(),
                label=value.strip(),
                color=os.getenv(f"PERSON_{raw_key}_COLOR", "").strip(),
                order=int(order_raw) if order_raw.lstrip("-").isdigit() else 100,
                feeds=tuple(f.lower() for f in _person_csv(raw_key, "FEEDS")),
                keywords=_person_csv(raw_key, "KEYWORDS"),
            )
        )
    found.sort(key=lambda p: (p.order, p.key))

    # Same palette fallback as feeds, skipping colours a feed or person claimed.
    claimed = [f.color for f in CALENDAR_FEEDS] + [p.color for p in found]
    used = {c.lower() for c in claimed if c}
    spare = (c for c in _FEED_PALETTE if c.lower() not in used)
    persons: list[Person] = []
    for p in found:
        fallback = _FEED_PALETTE[len(persons) % len(_FEED_PALETTE)]
        persons.append(p if p.color else replace(p, color=next(spare, fallback)))
    return tuple(persons)


#: Discovered persons, lowest PERSON_<KEY>_ORDER first.
PERSONS: tuple[Person, ...] = _load_persons()

#: Feeds whose events take the matched person's colour on the grid when exactly
#: one person matched (school / trash keep their feed colour regardless).
PERSON_COLOR_FEEDS: frozenset[str] = frozenset(
    k.lower() for k in _env_csv("PERSON_COLOR_FEEDS", "family")
)

#: The pool for the family line: events from these feeds that matched nobody.
FAMILY_FEEDS: frozenset[str] = frozenset(
    k.lower() for k in _env_csv("FAMILY_FEEDS", "family")
)
