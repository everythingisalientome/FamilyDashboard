"""EVENT_EXCLUDE_KEYWORDS (app/events_derived.is_excluded)."""

from app.events_derived import is_excluded

KEYWORDS = ("board of education", "school bond")


def test_match_is_case_insensitive_substring() -> None:
    assert is_excluded("Cabarrus Board of Education Meeting", KEYWORDS)
    assert is_excluded("SCHOOL BONDS info night", KEYWORDS)


def test_no_match_keeps_event() -> None:
    assert not is_excluded("Early Dismissal", KEYWORDS)
    assert not is_excluded(None, KEYWORDS)


def test_empty_keywords_exclude_nothing() -> None:
    assert not is_excluded("Board of Education Meeting", ())
