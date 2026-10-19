"""Which household member an event belongs to, and the colour it draws in.

Pure functions over event mappings (anything indexable by ``person``,
``source`` and ``title`` — an API event dict or a sqlite3.Row), so the rules
are unit-testable without a database. The roster and feed sets default to the
configured ones and can be passed in by tests.
"""

import re
from collections.abc import Collection
from functools import lru_cache
from typing import Any

from app.config import PERSON_COLOR_FEEDS, PERSONS, Person
from app.event_styles import compile_keywords

#: The importer's person value for "the whole family" — matches nobody.
FAMILY_TAG = "family"


@lru_cache(maxsize=None)
def _pattern(keywords: tuple[str, ...]) -> re.Pattern | None:
    """Word-boundary, case-insensitive matcher (event_styles' style)."""
    return compile_keywords(keywords) if keywords else None


def persons_for(event: Any, roster: tuple[Person, ...] = PERSONS) -> list[str]:
    """Keys of the persons ``event`` belongs to, in roster order.

    A DB ``person`` tag (the Google feed, Phase 4) wins outright; the tag
    ``family`` means nobody in particular (the family line). Otherwise an
    event belongs to everyone whose FEEDS list its source — so a school event
    belongs to every person in school — plus everyone named in its title.
    """
    tagged = (event["person"] or "").strip().lower()
    if tagged == FAMILY_TAG:  # the importer's explicit "whole family"
        return []
    if tagged:
        return [tagged]

    title = event["title"] or ""
    matched: list[str] = []
    for person in roster:
        pattern = _pattern(person.keywords)
        if event["source"] in person.feeds or (pattern and pattern.search(title)):
            matched.append(person.key)
    return matched


def display_color(
    event: Any,
    persons: list[str],
    feed_color: str,
    category_color: str | None,
    roster: tuple[Person, ...] = PERSONS,
    color_feeds: Collection[str] = PERSON_COLOR_FEEDS,
) -> str:
    """The grid colour: category, else the one matched person, else the feed.

    A person's colour only applies to events from ``color_feeds`` (the family
    calendar), so school and trash keep their feed colour even when they
    belong to someone.
    """
    if category_color:
        return category_color
    if event["source"] in color_feeds and len(persons) == 1:
        for person in roster:
            if person.key == persons[0]:
                return person.color
    return feed_color
