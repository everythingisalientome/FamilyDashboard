"""Admin "Add events": validate pasted extraction JSON, then write the reviewed
rows to the family Google Calendar.

The JSON comes from a chat model run with docs/event-extraction-prompt.md;
app/importer_rules.py checks the same contract. Validate never writes; commit
re-checks every row, so an invalid row can't reach Google whatever the page
sends. After a commit the family feed is re-read on a daemon thread, like the
admin refresh buttons. LAN-only, no auth (one household).
"""

import logging
import threading
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import gcal_client, gcal_writer
from app.config import DISPLAY_TZ, PERSONS
from app.envelope import envelope
from app.fetchers import gcal
from app.importer_rules import validate_row

router = APIRouter()
log = logging.getLogger("dashboard.importer")


class ValidateBody(BaseModel):
    person: str | None = None
    events: list[Any]


class CommitBody(BaseModel):
    rows: list[dict[str, Any]] = []
    delete_ids: list[str] = []


def _today() -> date:
    return datetime.now(DISPLAY_TZ).date()


def _require_calendar() -> None:
    problem = gcal_client.config_problem()
    if problem:
        raise HTTPException(status_code=503, detail=problem)


def _span(checked: list[dict[str, Any]]) -> tuple[date, date] | None:
    """First..last day any valid row (or its superseded event) touches."""
    days: list[str] = []
    for row in checked:
        norm = row["normalised"]
        if row["ok"]:
            days += [norm["date"], norm["end_date"] or norm["date"]]
            if norm["supersedes"]:
                days.append(norm["supersedes"]["date"])
    if not days:
        return None
    return date.fromisoformat(min(days)), date.fromisoformat(max(days))


@router.post("/admin/import/validate")
def import_validate(body: ValidateBody) -> dict[str, Any]:
    """Per row: ok, errors, warnings, past, exists, supersedes_id, normalised."""
    _require_calendar()
    today = _today()
    default = (body.person or "").strip().lower() or None
    roster = {p.key for p in PERSONS}
    checked = [validate_row(raw, default, today, roster) for raw in body.events]

    span = _span(checked)
    # One events.list over the whole window serves every row's checks.
    wall = gcal_writer.list_wall(span[0], span[1] + timedelta(days=1)) if span else []
    on_calendar = {item["id"] for item in wall}

    results: list[dict[str, Any]] = []
    for index, row in enumerate(checked):
        norm = row["normalised"]
        exists = bool(row["ok"] and norm["id"] in on_calendar)
        supersedes_id = None
        if row["ok"] and norm["supersedes"]:
            old = norm["supersedes"]
            supersedes_id = gcal_writer.find_supersedes(
                norm["person"], norm["title"], old["date"], old["start_time"], items=wall
            )
            if supersedes_id == norm["id"]:
                supersedes_id = None
                row["warnings"].append("same-day reschedule — change the time in Google Calendar")
            elif supersedes_id is None:
                row["warnings"].append(f"no earlier wall event found on {old['date']}")
        results.append({"index": index, **row, "exists": exists, "supersedes_id": supersedes_id})
    return envelope({"today": today.isoformat(), "rows": results})


@router.post("/admin/import/commit")
def import_commit(body: CommitBody) -> dict[str, Any]:
    """Insert the ticked rows, delete the ticked superseded events, re-read the feed."""
    _require_calendar()
    today = _today()
    roster = {p.key for p in PERSONS}
    errors: list[str] = []
    valid: list[dict[str, Any]] = []
    for raw in body.rows:
        row = validate_row(raw, None, today, roster)
        if row["ok"]:
            valid.append(row["normalised"])
        else:
            errors.append(f"{raw.get('title') or '?'}: {'; '.join(row['errors'])}")

    results = gcal_writer.insert_many(valid) if valid else []
    errors += [f"{r['message']}" for r in results if r["status"] == "error"]

    deleted = 0
    for eid in body.delete_ids:
        try:
            deleted += gcal_writer.delete(eid)
        except Exception as exc:
            errors.append(f"delete {eid}: {exc}")

    created = sum(r["status"] == "created" for r in results)
    exists = sum(r["status"] == "exists" for r in results)
    log.info("Import: %d created, %d exists, %d deleted, %d errors",
             created, exists, deleted, len(errors))
    if created or deleted:
        threading.Thread(target=gcal.run, name="refresh-gcal-import", daemon=True).start()
    return envelope({"created": created, "exists": exists, "errors": errors,
                     "deleted": deleted, "results": results})
