"""Closure alerts (app/alert_rules.py)."""

from datetime import date

from app.alert_rules import closure_records
from app.config import CLOSURE_ALERT_CATEGORIES

WEDNESDAY = date(2026, 11, 25)


def row(title: str, day: str = "2026-11-25") -> dict:
    return {"title": title, "start_date_local": day, "end_date_local": day}


def test_default_includes_dismissal() -> None:
    assert {"school", "holiday", "dismissal"} <= CLOSURE_ALERT_CATEGORIES


def test_early_dismissal_day_raises_closure_alert() -> None:
    records = closure_records(
        [row("Closes 12:00 – Family Luncheon"), row("Picture day")], WEDNESDAY
    )
    assert [r["kind"] for r in records] == ["closure"]
    assert records[0]["title"] == "Closes 12:00 – Family Luncheon"
    assert records[0]["tone"] == "red"
