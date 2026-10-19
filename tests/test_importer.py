"""JSON importer: rules (pure), writer and API against a fake Google service."""

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import gcal_client, gcal_writer
from app.api import importer
from app.importer_rules import decorate_title, shift_months, validate_row

TODAY = date(2026, 10, 18)
ROSTER = {"prisha", "prapti"}


def row(**over: Any) -> dict[str, Any]:
    base = {"person": "prapti", "kind": "event", "title": "Picture Day",
            "date": "2026-11-05", "end_date": None, "all_day": True,
            "start_time": None, "end_time": None, "location": None,
            "notes": None, "supersedes": None, "confidence": "high"}
    return {**base, **over}


def check(raw: Any, person: str | None = None) -> dict[str, Any]:
    return validate_row(raw, person, TODAY, ROSTER)


# --- rules -----------------------------------------------------------------


def test_valid_row_normalises_with_deterministic_id() -> None:
    got = check(row())
    assert got["ok"] and not got["errors"] and not got["past"]
    norm = got["normalised"]
    assert norm["id"] == gcal_writer.event_id("prapti", "2026-11-05", "Picture Day")
    assert len(norm["id"]) == 31
    assert all(c in "0123456789abcdefghijklmnopqrstuv" for c in norm["id"])  # base32hex


def test_required_keys_and_enums() -> None:
    got = check({"title": "x", "kind": "party"})
    assert not got["ok"]
    assert "missing date" in got["errors"]
    assert any(e.startswith("kind must be") for e in got["errors"])


def test_person_falls_back_to_request_then_errors() -> None:
    assert check(row(person=None), "Prisha")["normalised"]["person"] == "prisha"
    assert "no person" in check(row(person=None))["errors"]
    assert "unknown person 'bob'" in check(row(person="bob"))["errors"]
    assert check(row(person="family"))["ok"]


def test_dates_window_and_order() -> None:
    assert check(row(date="2026-13-01"))["errors"][0].startswith("date is not")
    assert "date is more than 18 months from today" in check(row(date="2028-06-01"))["errors"]
    assert "end_date is before date" in check(row(end_date="2026-11-01"))["errors"]
    assert check(row(date="2026-10-12"))["past"] is True
    assert shift_months(date(2026, 8, 31), 18) == date(2028, 2, 29)


def test_times() -> None:
    assert "a timed event needs start_time" in check(row(all_day=False))["errors"]
    bad = check(row(all_day=False, start_time="9:00"))
    assert bad["errors"] == ["start_time is not a 24h HH:MM time: '9:00'"]
    assert "end_time is not after start_time" in check(
        row(all_day=False, start_time="10:00", end_time="09:00"))["errors"]
    ignored = check(row(start_time="10:00"))
    assert ignored["ok"] and ignored["normalised"]["start_time"] is None
    assert ignored["warnings"]


def test_title_rules_and_conventions() -> None:
    assert "title is empty" in check(row(title="  "))["errors"]
    assert "title is over 80 characters" in check(row(title="x" * 81))["errors"]
    closed = check(row(kind="closed", title="Thanksgiving Day"))["normalised"]
    assert closed["title"] == "Daycare closed – Thanksgiving Day"
    early = check(row(kind="early_close", title="Family Luncheon", all_day=False,
                      start_time="12:00"))["normalised"]
    assert early["title"] == "Closes 12:00 – Family Luncheon"
    # idempotent; not daycare -> unchanged
    assert decorate_title("closed", closed["title"], "prapti", None) == closed["title"]
    assert decorate_title("closed", "Thanksgiving", "prisha", None) == "Thanksgiving"


def test_skipped_and_garbage_rows_are_errors_not_dropped() -> None:
    assert check({"skipped": "blurry May"})["errors"] == ["skipped by the extractor: blurry May"]
    assert check("nope")["errors"] == ["not a JSON object"]


def test_closes_lands_in_school_and_daycare_closed_in_holiday() -> None:
    from app.event_styles import categorize
    assert categorize("Closes 12:00 – Family Luncheon").key == "school"
    assert categorize("Daycare closed – Thanksgiving Day").key == "holiday"


# --- writer ----------------------------------------------------------------


class HttpError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.resp = SimpleNamespace(status=status)


class Call:
    def __init__(self, fn: Any) -> None:
        self.fn = fn

    def execute(self) -> Any:
        return self.fn()


class FakeCalendar:
    """In-memory events resource: insert/get/update/delete/list."""

    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.list_calls: list[dict[str, Any]] = []

    def events(self) -> "FakeCalendar":
        return self

    def insert(self, calendarId: str, body: dict, sendUpdates: str) -> Call:
        assert sendUpdates == "none"

        def run() -> dict:
            if body["id"] in self.store:
                raise HttpError(409)
            self.store[body["id"]] = {**body, "status": "confirmed"}
            return body
        return Call(run)

    def get(self, calendarId: str, eventId: str) -> Call:
        def run() -> dict:
            if eventId not in self.store:
                raise HttpError(404)
            return self.store[eventId]
        return Call(run)

    def update(self, calendarId: str, eventId: str, body: dict, sendUpdates: str) -> Call:
        return Call(lambda: self.store.__setitem__(eventId, body))

    def delete(self, calendarId: str, eventId: str, sendUpdates: str) -> Call:
        return Call(lambda: self.store[eventId].__setitem__("status", "cancelled"))

    def list(self, **params: Any) -> Call:
        self.list_calls.append(params)
        assert params["privateExtendedProperty"] == "source=wall"
        return Call(lambda: {"items": list(self.store.values())})


@pytest.fixture
def cal(monkeypatch: pytest.MonkeyPatch) -> FakeCalendar:
    fake = FakeCalendar()
    monkeypatch.setattr(gcal_client, "build_service", lambda: fake)
    monkeypatch.setattr(gcal_client, "config_problem", lambda: None)
    return fake


def test_to_google_all_day_and_timed() -> None:
    allday = gcal_writer.to_google(check(row(end_date="2026-11-06"))["normalised"])
    assert allday["start"] == {"date": "2026-11-05"} and allday["end"] == {"date": "2026-11-07"}
    assert allday["summary"] == "Picture Day"
    assert allday["extendedProperties"]["private"] == {
        "source": "wall", "person": "prapti", "kind": "event"}
    assert allday["reminders"] == {"useDefault": False}
    timed = gcal_writer.to_google(check(row(
        all_day=False, start_time="08:40", location="Peds", notes="Dr G"))["normalised"])
    assert timed["start"]["dateTime"] == "2026-11-05T08:40:00-05:00"
    assert timed["end"]["dateTime"] == "2026-11-05T09:40:00-05:00"
    assert timed["start"]["timeZone"] == "America/New_York"
    assert (timed["location"], timed["description"]) == ("Peds", "Dr G")


def test_insert_twice_is_exists_and_deleted_id_is_restored(cal: FakeCalendar) -> None:
    norm = check(row())["normalised"]
    assert [r["status"] for r in gcal_writer.insert_many([norm])] == ["created"]
    assert [r["status"] for r in gcal_writer.insert_many([norm])] == ["exists"]
    assert len(cal.store) == 1
    assert gcal_writer.delete(norm["id"]) is True
    assert gcal_writer.delete(norm["id"]) is False  # already cancelled
    assert [r["status"] for r in gcal_writer.insert_many([norm])] == ["created"]
    assert cal.store[norm["id"]]["status"] == "confirmed"


def test_delete_refuses_non_wall_and_missing(cal: FakeCalendar) -> None:
    cal.store["handmade"] = {"id": "handmade", "status": "confirmed", "summary": "Dentist"}
    with pytest.raises(PermissionError):
        gcal_writer.delete("handmade")
    assert cal.store["handmade"]["status"] == "confirmed"
    assert gcal_writer.delete("nope") is False


def test_find_supersedes_matches_person_title_date(cal: FakeCalendar) -> None:
    old = check(row(kind="appointment", title="Well Child", date="2026-11-03",
                    all_day=False, start_time="09:00"))["normalised"]
    gcal_writer.insert_many([old])
    assert gcal_writer.find_supersedes("prapti", "well child", "2026-11-03", "09:00") == old["id"]
    assert gcal_writer.find_supersedes("prisha", "Well Child", "2026-11-03", None) is None
    assert gcal_writer.find_supersedes("prapti", "Well Child", "2026-11-04", None) is None


# --- API -------------------------------------------------------------------


@pytest.fixture
def client(cal: FakeCalendar, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.main import app
    monkeypatch.setattr(importer, "_today", lambda: TODAY)
    monkeypatch.setattr(importer.gcal, "run", lambda: None)
    return TestClient(app)


def test_validate_flags_exists_past_and_supersedes(client: TestClient, cal: FakeCalendar) -> None:
    old = check(row(kind="appointment", title="Well Child", date="2026-11-03",
                    all_day=False, start_time="09:00"))["normalised"]
    gcal_writer.insert_many([old, check(row())["normalised"]])
    cal.list_calls.clear()
    events = [
        row(person=None),                                     # exists, person from request
        row(date="2026-10-12", title="Old thing"),            # past
        row(kind="appointment", title="Well Child", date="2026-11-10", all_day=False,
            start_time="08:40", supersedes={"date": "2026-11-03", "start_time": "09:00"}),
        {"skipped": "unreadable"},
    ]
    res = client.post("/api/admin/import/validate", json={"person": "prapti", "events": events})
    data = res.json()["data"]["rows"]
    assert len(cal.list_calls) == 1  # one list per request
    assert [r["index"] for r in data] == [0, 1, 2, 3]
    assert data[0]["ok"] and data[0]["exists"]
    assert data[1]["past"] and not data[1]["exists"]
    assert data[2]["supersedes_id"] == old["id"]
    assert not data[3]["ok"] and data[3]["errors"]


def test_commit_creates_then_exists_and_deletes(client: TestClient, cal: FakeCalendar) -> None:
    rows = [check(row())["normalised"], check(row(title="Second"))["normalised"]]
    first = client.post("/api/admin/import/commit", json={"rows": rows}).json()["data"]
    assert (first["created"], first["exists"], first["errors"]) == (2, 0, [])
    again = client.post("/api/admin/import/commit", json={"rows": rows}).json()["data"]
    assert (again["created"], again["exists"]) == (0, 2)
    assert len(cal.store) == 2

    bad = {**rows[0], "date": "nope"}
    gone = client.post("/api/admin/import/commit",
                       json={"rows": [bad], "delete_ids": [rows[1]["id"]]}).json()["data"]
    assert gone["deleted"] == 1 and gone["created"] == 0 and len(gone["errors"]) == 1
    assert cal.store[rows[1]["id"]]["status"] == "cancelled"
