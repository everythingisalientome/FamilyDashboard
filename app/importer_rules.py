"""Pure validation for the JSON importer — the server side of the contract in
docs/event-extraction-prompt.md. No network, no database: one raw row in,
``{ok, errors, warnings, past, normalised}`` out.

Required keys are ``kind``, ``title`` and ``date``; every other key in the
prompt's schema may be missing and is read as null (models drop null keys).
"""

import re
from calendar import monthrange
from collections.abc import Collection
from datetime import date
from typing import Any

from app.config import IMPORT_DAYCARE_PERSONS
from app.gcal_writer import event_id
from app.persons import FAMILY_TAG

KINDS = ("closed", "early_close", "appointment", "event")
CONFIDENCES = ("high", "medium", "low")
REQUIRED = ("kind", "title", "date")
TITLE_MAX = 80
WINDOW_MONTHS = 18

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def shift_months(day: date, months: int) -> date:
    """``day`` moved by ``months``, clamped to the target month's length."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def decorate_title(kind: str, title: str, person: str, start_time: str | None,
                   daycare: Collection[str] = IMPORT_DAYCARE_PERSONS) -> str:
    """The PLAN's title conventions, idempotent so an edited title survives.

    ``closed`` for a daycare person -> "Daycare closed – <title>" (holiday
    category); ``early_close`` -> "Closes 12:00 – <title>" (school category).
    """
    low = title.lower()
    if kind == "closed" and person in daycare and "closed" not in low:
        return f"Daycare closed – {title}"
    if kind == "early_close" and not low.startswith("closes"):
        return f"Closes {start_time or 'early'} – {title}"
    return title


def _date(value: Any, name: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and _DATE.match(value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    errors.append(f"{name} is not a valid YYYY-MM-DD date: {value!r}")
    return None


def _time(value: Any, name: str, errors: list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and _TIME.match(value.strip()):
        return value.strip()
    errors.append(f"{name} is not a 24h HH:MM time: {value!r}")
    return None


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def validate_row(raw: Any, default_person: str | None, today: date,
                 persons: Collection[str]) -> dict[str, Any]:
    """Check one raw row and normalise it. Rows with errors are still returned."""
    errors: list[str] = []
    warnings: list[str] = []
    out: dict[str, Any] = {"ok": False, "errors": errors, "warnings": warnings,
                           "past": False, "normalised": None}
    if not isinstance(raw, dict):
        errors.append("not a JSON object")
        return out
    if "skipped" in raw and "date" not in raw:
        errors.append(f"skipped by the extractor: {raw.get('skipped')}")
        return out
    errors.extend(f"missing {key}" for key in REQUIRED if key not in raw)

    person = (_text(raw.get("person")) or default_person or "").lower()
    if not person:
        errors.append("no person")
    elif person not in persons and person != FAMILY_TAG:
        errors.append(f"unknown person {person!r}")

    kind = raw.get("kind")
    if "kind" in raw and kind not in KINDS:
        errors.append(f"kind must be one of {', '.join(KINDS)}")

    first = _date(raw.get("date"), "date", errors)
    last = _date(raw.get("end_date"), "end_date", errors)
    start_time = _time(raw.get("start_time"), "start_time", errors)
    end_time = _time(raw.get("end_time"), "end_time", errors)

    all_day = raw.get("all_day", start_time is None)
    if not isinstance(all_day, bool):
        errors.append("all_day must be true or false")
        all_day = start_time is None

    title = _text(raw.get("title"))
    if "title" in raw and not title:
        errors.append("title is empty")
    if title and isinstance(kind, str):
        title = decorate_title(kind, title, person, start_time)
    if title and len(title) > TITLE_MAX:
        errors.append(f"title is over {TITLE_MAX} characters")

    if first:
        day = date.fromisoformat(first)
        if not shift_months(today, -WINDOW_MONTHS) <= day <= shift_months(today, WINDOW_MONTHS):
            errors.append(f"date is more than {WINDOW_MONTHS} months from today")
        out["past"] = day < today
    if first and last:
        if last < first:
            errors.append("end_date is before date")
        elif last == first:
            last = None
    if all_day and (start_time or end_time):
        warnings.append("all-day event: the times were ignored")
        start_time = end_time = None
    if not all_day and raw.get("start_time") is None:
        errors.append("a timed event needs start_time")
    if start_time and end_time and not last and end_time <= start_time:
        errors.append("end_time is not after start_time")

    supersedes = raw.get("supersedes")
    old: dict[str, Any] | None = None
    if isinstance(supersedes, dict):
        if supersedes.get("date"):
            scratch: list[str] = []
            old = {"date": _date(supersedes.get("date"), "supersedes.date", scratch),
                   "start_time": _time(supersedes.get("start_time"), "supersedes.start_time", scratch)}
            warnings.extend(scratch)
            if not old["date"]:
                old = None
        else:
            warnings.append("rescheduled, but the old date is missing — remove the old event by hand")

    confidence = raw.get("confidence")
    if confidence == "low":
        warnings.append("low confidence — check the date and title")
    elif confidence is not None and confidence not in CONFIDENCES:
        warnings.append(f"unknown confidence {confidence!r}")

    # Error rows keep what parsed (no id), so the review table can show them.
    out["ok"] = not errors
    out["normalised"] = {
        "id": event_id(person, first, title) if not errors else None,
        "person": person, "kind": kind, "title": title,
        "date": first, "end_date": last, "all_day": all_day,
        "start_time": start_time, "end_time": end_time,
        "location": _text(raw.get("location")), "notes": _text(raw.get("notes")),
        "supersedes": old, "confidence": confidence,
    }
    return out
