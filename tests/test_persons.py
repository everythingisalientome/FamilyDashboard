"""Person attribution and grid colour rules (app/persons.py)."""

from app.config import Person
from app.persons import display_color, persons_for

PRISHA = Person("prisha", "Prisha", "#19b2d8", 1, ("school",), ("prisha",))
PRAPTI = Person("prapti", "Prapti", "#bc39bd", 2, (), ("prapti",))
ROSTER = (PRISHA, PRAPTI)


def ev(title: str, source: str = "family", person: str | None = None) -> dict:
    return {"title": title, "source": source, "person": person}


def test_feed_attribution() -> None:
    assert persons_for(ev("Picture day", "school"), ROSTER) == ["prisha"]


def test_feed_belongs_to_everyone_listing_it() -> None:
    both = (PRISHA, Person("prapti", "Prapti", "#bc39bd", 2, ("school",), ()))
    assert persons_for(ev("Picture day", "school"), both) == ["prisha", "prapti"]


def test_keyword_attribution_is_word_boundary_and_case_insensitive() -> None:
    assert persons_for(ev("PRAPTI dentist"), ROSTER) == ["prapti"]
    assert persons_for(ev("Praptinagar trip"), ROSTER) == []
    assert persons_for(ev("Dinner out"), ROSTER) == []


def test_feed_and_keyword_together_dedupe_in_roster_order() -> None:
    # Prapti named in a school event: both, Prisha first and only once.
    event = ev("Prapti and Prisha pickup", "school")
    assert persons_for(event, ROSTER) == ["prisha", "prapti"]


def test_db_column_overrides_feed_and_keywords() -> None:
    event = ev("Prisha recital", "school", person="prapti")
    assert persons_for(event, ROSTER) == ["prapti"]


def colour(event: dict, cat: str | None = None) -> str:
    persons = persons_for(event, ROSTER)
    return display_color(event, persons, "#feed00", cat, ROSTER, {"family"})


def test_category_colour_wins() -> None:
    assert colour(ev("Prisha holiday"), cat="#ff6b6b") == "#ff6b6b"


def test_single_person_on_colour_feed_takes_person_colour() -> None:
    assert colour(ev("Prapti swim")) == "#bc39bd"


def test_db_tagged_person_takes_their_colour() -> None:
    assert colour(ev("Swim", person="prisha")) == "#19b2d8"


def test_two_persons_or_none_keep_feed_colour() -> None:
    assert colour(ev("Prisha and Prapti swim")) == "#feed00"
    assert colour(ev("Dinner out")) == "#feed00"


def test_non_colour_feed_keeps_feed_colour_even_with_one_person() -> None:
    assert colour(ev("Picture day", "school")) == "#feed00"
