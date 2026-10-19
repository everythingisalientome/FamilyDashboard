"""Google Calendar family feed (app/fetchers/gcal.py) against a fake service."""

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app import db
from app.config import Person
from app.events_derived import hero
from app.fetchers import gcal
from app.persons import persons_for

PAGE_1 = {
    "items": [
        {  # all-day, two days (Oct 26-27); Google's end.date is exclusive
            "id": "allday1", "status": "confirmed", "summary": "Fall break",
            "start": {"date": "2026-10-26"}, "end": {"date": "2026-10-28"},
        },
        {  # timed, tagged by the importer
            "id": "timed1", "status": "confirmed", "summary": "Well-child visit",
            "location": "Pediatrics", "description": "Bring the shot record",
            "start": {"dateTime": "2026-10-20T10:00:00-04:00"},
            "end": {"dateTime": "2026-10-20T10:30:00-04:00"},
            "extendedProperties": {"private": {"person": "Prapti", "kind": "appointment"}},
        },
        {  # cancelled instance — skipped
            "id": "gone", "status": "cancelled",
            "start": {"dateTime": "2026-10-21T09:00:00-04:00"},
            "end": {"dateTime": "2026-10-21T10:00:00-04:00"},
        },
    ],
    "nextPageToken": "page2",
}

PAGE_2 = {
    "items": [
        {  # Gmail-created — kept; no title; UTC 'Z' times
            "id": "gmail1", "status": "confirmed", "eventType": "fromGmail",
            "start": {"dateTime": "2026-10-22T23:30:00Z"},
            "end": {"dateTime": "2026-10-23T01:00:00Z"},
        },
    ],
}


class FakeList:
    def __init__(self, page: dict[str, Any]) -> None:
        self.page = page

    def execute(self) -> dict[str, Any]:
        return self.page


class FakeEvents:
    def __init__(self, service: "FakeService") -> None:
        self.service = service

    def list(self, **params: Any) -> FakeList:
        self.service.calls.append(params)
        return FakeList(PAGE_2 if params.get("pageToken") == "page2" else PAGE_1)


class FakeService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def events(self) -> FakeEvents:
        return FakeEvents(self)


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return tmp_path


@pytest.fixture
def configured(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> FakeService:
    key = temp_db / "sa.json"
    key.write_text("{}")
    service = FakeService()
    monkeypatch.setattr(gcal, "GCAL_CALENDAR_ID", "family@example.com")
    monkeypatch.setattr(gcal, "GCAL_SERVICE_ACCOUNT_FILE", key)
    monkeypatch.setattr(gcal, "_build_service", lambda: service)
    return service


def rows() -> dict[str, dict[str, Any]]:
    with db.connect() as conn:
        found = conn.execute("SELECT * FROM events").fetchall()
    return {r["uid"]: dict(r) for r in found}


def meta() -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM fetch_meta WHERE job = ?", (gcal.JOB,)).fetchone()
    return dict(row) if row else {}


def test_run_writes_rows_and_follows_pages(configured: FakeService) -> None:
    gcal.run()

    assert [c.get("pageToken") for c in configured.calls] == [None, "page2"]
    first = configured.calls[0]
    assert first["calendarId"] == "family@example.com"
    assert first["singleEvents"] is True and first["orderBy"] == "startTime"
    assert first["timeZone"] == "America/New_York"

    got = rows()
    assert set(got) == {"allday1", "timed1", "gmail1"}  # cancelled skipped
    assert {r["source"] for r in got.values()} == {"family"}
    assert meta()["last_success_utc"] and meta()["last_error"] is None


def test_all_day_end_is_exclusive(configured: FakeService) -> None:
    gcal.run()
    row = rows()["allday1"]
    assert row["all_day"] == 1
    assert (row["start_date_local"], row["end_date_local"]) == ("2026-10-26", "2026-10-27")
    assert row["start_time_local"] is None
    assert row["person"] is None and row["kind"] is None


def test_timed_converts_to_utc_and_carries_tags(configured: FakeService) -> None:
    gcal.run()
    row = rows()["timed1"]
    assert row["all_day"] == 0
    assert row["start_utc"] == "2026-10-20T14:00:00+00:00"
    assert row["end_utc"] == "2026-10-20T14:30:00+00:00"
    assert (row["start_date_local"], row["start_time_local"]) == ("2026-10-20", "10:00")
    assert row["person"] == "prapti" and row["kind"] == "appointment"
    assert row["location"] == "Pediatrics"
    assert row["description"] == "Bring the shot record"


def test_gmail_event_kept_untitled_and_localised(configured: FakeService) -> None:
    gcal.run()
    row = rows()["gmail1"]
    assert row["title"] == "(No title)"
    # 23:30Z is 19:30 EDT, still Oct 22 locally.
    assert (row["start_date_local"], row["start_time_local"]) == ("2026-10-22", "19:30")


def test_missing_key_file_records_failure_and_keeps_rows(
    configured: FakeService, temp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gcal.run()
    before = rows()
    monkeypatch.setattr(gcal, "GCAL_SERVICE_ACCOUNT_FILE", temp_db / "missing.json")

    gcal.run()

    assert rows() == before
    assert "service account key not found" in meta()["last_error"]
    assert len(configured.calls) == 2  # the second run never reached the API


def test_api_error_records_failure_and_keeps_rows(
    configured: FakeService, monkeypatch: pytest.MonkeyPatch
) -> None:
    gcal.run()
    before = rows()

    def boom() -> Any:
        raise RuntimeError("HTTP 503")

    monkeypatch.setattr(gcal, "_build_service", boom)
    gcal.run()  # must not raise

    assert rows() == before
    assert meta()["last_error"] == "RuntimeError: HTTP 503"


# --- attribution: the person tag lands the event in that person's hero ------

PRISHA = Person("prisha", "Prisha", "#19b2d8", 1, ("school",), ("prisha",))
PRAPTI = Person("prapti", "Prapti", "#bc39bd", 2, (), ("prapti",))
ROSTER = (PRISHA, PRAPTI)


def as_event(item: dict[str, Any]) -> dict[str, Any]:
    row = {**gcal.to_row(item), "source": "family"}
    return {
        "source": "family", "title": row["title"], "start_utc": row["start_utc"],
        "end_utc": row["end_utc"], "start_date": row["start_date_local"],
        "end_date": row["end_date_local"], "all_day": bool(row["all_day"]),
        "category": None, "persons": persons_for(row, ROSTER),
    }


def test_tagged_row_goes_to_person_untagged_to_family() -> None:
    tagged, untitled_family = PAGE_1["items"][1], PAGE_1["items"][0]
    events = [as_event(tagged), as_event(untitled_family)]
    today, now = date(2026, 10, 18), datetime(2026, 10, 18, 16, tzinfo=timezone.utc)

    out = hero(events, today, now, ROSTER, {"family"})

    prapti = next(c for c in out["persons"] if c["key"] == "prapti")
    assert prapti["next"]["title"] == "Well-child visit"
    assert out["family"]["next"]["title"] == "Fall break"
    prisha = next(c for c in out["persons"] if c["key"] == "prisha")
    assert prisha["next"] is None


# --- config: family is the Google feed, never ICS --------------------------


def test_family_feed_comes_from_gcal_id_not_cal_family_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import feeds

    monkeypatch.setenv("CAL_FAMILY_URL", "https://example.com/retired.ics")
    monkeypatch.setenv("CAL_FAMILY_COLOR", "#123456")
    monkeypatch.setattr(feeds, "GCAL_CALENDAR_ID", "")
    assert "family" not in {f.key for f in feeds._load_calendar_feeds()}

    monkeypatch.setattr(feeds, "GCAL_CALENDAR_ID", "family@example.com")
    family = next(f for f in feeds._load_calendar_feeds() if f.key == "family")
    assert (family.url, family.color) == ("", "#123456")


def test_ics_fetcher_skips_blank_url_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import CalendarFeed
    from app.fetchers import calendars

    fetched: list[str] = []
    monkeypatch.setattr(
        calendars, "CALENDAR_FEEDS",
        (CalendarFeed("family", "Family", "", "#fff"),
         CalendarFeed("school", "School", "https://x/s.ics", "#000")),
    )
    monkeypatch.setattr(calendars, "_refresh_feed", lambda feed, s, e: fetched.append(feed.key))
    calendars.run()
    assert fetched == ["school"]
