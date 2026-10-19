"""Built-in event categories and their precedence (app/event_styles.py)."""

from app.event_styles import EVENT_CATEGORIES, categorize


def key(title: str) -> str | None:
    category = categorize(title)
    return category.key if category else None


def test_dismissal_and_school_are_separate() -> None:
    assert key("Early Dismissal for traditional calendar students") == "dismissal"
    assert key("Early Release Day") == "dismissal"
    assert key("Half Day") == "dismissal"
    assert key("Closes 12:00 – Family Luncheon") == "dismissal"
    assert key("First Day of School") == "school"
    assert key("Last day of school") == "school"


def test_dismissal_outranks_quarter() -> None:
    assert key("End of Quarter/Early Dismissal for traditional calendar students") == "dismissal"
    assert key("End of Quarter") == "quarter"


def test_dismissal_and_school_share_gold_and_precede_holiday() -> None:
    by_key = {c.key: c for c in EVENT_CATEGORIES}
    assert by_key["dismissal"].color == by_key["school"].color
    order = [c.key for c in EVENT_CATEGORIES]
    assert order.index("dismissal") < order.index("quarter") < order.index("school")
    assert order.index("school") < order.index("holiday")


def test_env_overrides_apply_to_both(monkeypatch) -> None:
    from app.event_styles import _load

    monkeypatch.setenv("EVENT_STYLE_DISMISSAL_COLOR", "#123456")
    monkeypatch.setenv("EVENT_STYLE_DISMISSAL_KEYWORDS", "late start")
    monkeypatch.setenv("EVENT_STYLE_SCHOOL_ORDER", "1")
    by_key = {c.key: c for c in _load()}
    assert by_key["dismissal"].color == "#123456"
    assert by_key["dismissal"].matches("Late Start Wednesday")
    assert by_key["school"].order == 1
