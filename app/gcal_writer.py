"""Write importer rows to the family Google Calendar. No FastAPI here.

Every event this module creates carries ``extendedProperties.private.source =
"wall"`` and a deterministic id derived from person|date|title, so re-pasting
the same JSON is a no-op ("exists"), never a duplicate. Deletes refuse any
event without the wall tag — hand-entered events are never touched.

Rows are the importer's normalised rows (app/importer_rules.py): ``person``,
``kind``, ``title``, ``date``, ``end_date``, ``all_day``, ``start_time``,
``end_time``, ``location``, ``notes`` — dates/times as ISO strings.
"""

import hashlib
import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from app import gcal_client
from app.config import DISPLAY_TZ, DISPLAY_TZ_NAME, GCAL_CALENDAR_ID

log = logging.getLogger("dashboard.gcal_writer")

WALL_SOURCE = "wall"

#: A timed row with no end_time gets this long on the calendar.
DEFAULT_DURATION = timedelta(hours=1)

_MAX_PAGES = 20


#: Id prefix. Google ids must be base32hex (0-9, a-v): "wall" is not ("w").
ID_PREFIX = "fam"


def event_id(person: str, day: str, title: str) -> str:
    """Deterministic Google-valid id: prefix + 28 lowercase hex (base32hex-safe)."""
    key = f"{person}|{day}|{title.lower().strip()}"
    return ID_PREFIX + hashlib.sha1(key.encode("utf-8")).hexdigest()[:28]


def _local(day: str, hhmm: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(hhmm), DISPLAY_TZ)


def to_google(row: dict[str, Any]) -> dict[str, Any]:
    """One normalised row -> a Calendar events.insert body."""
    first = row["date"]
    last = row.get("end_date") or first
    if row["all_day"]:
        # Google's all-day end.date is exclusive: the day after the last day.
        end_excl = (date.fromisoformat(last) + timedelta(days=1)).isoformat()
        start: dict[str, str] = {"date": first}
        end: dict[str, str] = {"date": end_excl}
    else:
        begins = _local(first, row["start_time"])
        if row.get("end_time"):
            ends = _local(last, row["end_time"])
        else:
            ends = _local(last, row["start_time"]) + DEFAULT_DURATION
        start = {"dateTime": begins.isoformat(), "timeZone": DISPLAY_TZ_NAME}
        end = {"dateTime": ends.isoformat(), "timeZone": DISPLAY_TZ_NAME}

    body: dict[str, Any] = {
        "id": event_id(row["person"], first, row["title"]),
        "summary": row["title"],
        "start": start,
        "end": end,
        "extendedProperties": {
            "private": {"source": WALL_SOURCE, "person": row["person"], "kind": row["kind"]}
        },
        "reminders": {"useDefault": False},
    }
    if row.get("location"):
        body["location"] = row["location"]
    if row.get("notes"):
        body["description"] = row["notes"]
    return body


def _events(service: Any | None) -> Any:
    return (service or gcal_client.build_service()).events()


def insert_many(rows: list[dict[str, Any]], service: Any | None = None) -> list[dict[str, Any]]:
    """Insert each row; per row ``{id, status: created|exists|error, message}``.

    A 409 means the id is taken. If that event was deleted earlier (Google
    keeps cancelled ids), it is restored instead — still "created".
    """
    events = _events(service)
    results: list[dict[str, Any]] = []
    for row in rows:
        body = to_google(row)
        eid = body["id"]
        try:
            events.insert(calendarId=GCAL_CALENDAR_ID, body=body, sendUpdates="none").execute()
            results.append({"id": eid, "status": "created", "message": row["title"]})
        except Exception as exc:
            if gcal_client.http_status(exc) == 409:
                results.append(_on_conflict(events, eid, body, row["title"]))
            else:
                log.warning("Insert %s failed: %s", eid, exc)
                results.append({"id": eid, "status": "error", "message": str(exc)})
    return results


def _on_conflict(events: Any, eid: str, body: dict[str, Any], title: str) -> dict[str, Any]:
    try:
        current = events.get(calendarId=GCAL_CALENDAR_ID, eventId=eid).execute()
        if current.get("status") != "cancelled":
            return {"id": eid, "status": "exists", "message": title}
        events.update(
            calendarId=GCAL_CALENDAR_ID, eventId=eid,
            body={**body, "status": "confirmed"}, sendUpdates="none",
        ).execute()
        return {"id": eid, "status": "created", "message": f"{title} (restored)"}
    except Exception as exc:
        log.warning("Conflict on %s could not be resolved: %s", eid, exc)
        return {"id": eid, "status": "error", "message": str(exc)}


def delete(eid: str, service: Any | None = None) -> bool:
    """Delete a wall-created event. False if missing; raises on a non-wall one."""
    events = _events(service)
    try:
        current = events.get(calendarId=GCAL_CALENDAR_ID, eventId=eid).execute()
    except Exception as exc:
        if gcal_client.http_status(exc) in (404, 410):
            return False
        raise
    if current.get("status") == "cancelled":
        return False
    private = (current.get("extendedProperties") or {}).get("private") or {}
    if private.get("source") != WALL_SOURCE:
        raise PermissionError(f"{eid} was not created by the wall; refusing to delete")
    try:
        events.delete(calendarId=GCAL_CALENDAR_ID, eventId=eid, sendUpdates="none").execute()
    except Exception as exc:
        if gcal_client.http_status(exc) in (404, 410):
            return False
        raise
    return True


def list_wall(first: date, last: date, service: Any | None = None) -> list[dict[str, Any]]:
    """Every live wall-tagged event touching first..last (inclusive)."""
    params: dict[str, Any] = {
        "calendarId": GCAL_CALENDAR_ID,
        "timeMin": datetime.combine(first, time(0, 0), DISPLAY_TZ).isoformat(),
        "timeMax": datetime.combine(last + timedelta(days=1), time(0, 0), DISPLAY_TZ).isoformat(),
        "privateExtendedProperty": f"source={WALL_SOURCE}",
        "singleEvents": True,
        "timeZone": DISPLAY_TZ_NAME,
        "maxResults": 250,
    }
    events = _events(service)
    items: list[dict[str, Any]] = []
    for _ in range(_MAX_PAGES):
        page = events.list(**params).execute()
        items.extend(page.get("items", []))
        if not page.get("nextPageToken"):
            break
        params["pageToken"] = page["nextPageToken"]
    return [i for i in items if i.get("status") != "cancelled"]


def find_supersedes(
    person: str, title: str, day: str, start_time: str | None,
    items: list[dict[str, Any]] | None = None, service: Any | None = None,
) -> str | None:
    """The wall event on ``day`` with the same person + title, or None.

    ``items`` is an already-fetched ``list_wall`` result (the importer caches
    one per request); otherwise that one day is listed. With several matches,
    the one at ``start_time`` wins.
    """
    if items is None:
        when = date.fromisoformat(day)
        items = list_wall(when, when, service)
    want = title.lower().strip()
    found: list[dict[str, Any]] = []
    for item in items:
        private = (item.get("extendedProperties") or {}).get("private") or {}
        start = item.get("start") or {}
        on = start.get("date") or (start.get("dateTime") or "")[:10]
        if (on == day and private.get("person") == person
                and (item.get("summary") or "").lower().strip() == want):
            found.append(item)
    for item in found:
        if start_time and (item["start"].get("dateTime") or "")[11:16] == start_time:
            return item["id"]
    return found[0]["id"] if found else None
