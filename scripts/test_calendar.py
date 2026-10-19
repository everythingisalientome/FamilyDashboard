"""Does the Google Calendar service account work? Run from the repo root:

    .venv\\Scripts\\python.exe scripts\\test_calendar.py           # read check
    .venv\\Scripts\\python.exe scripts\\test_calendar.py --write   # + insert/delete

Reads GCAL_CALENDAR_ID and GCAL_SERVICE_ACCOUNT_FILE from .env (via
app.config, so it checks exactly what the server will use) and lists the next
10 events. ``--write`` also inserts a test event tomorrow at 10:00 and deletes
it again, proving the calendar is shared as "Make changes to events".
"""

import argparse
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.oauth2 import service_account  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

from app.config import (  # noqa: E402
    DISPLAY_TZ,
    DISPLAY_TZ_NAME,
    GCAL_CALENDAR_ID,
    GCAL_SCOPES,
    GCAL_SERVICE_ACCOUNT_FILE,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="also insert + delete a test event")
    args = parser.parse_args()

    if not GCAL_CALENDAR_ID:
        print("GCAL_CALENDAR_ID is not set in .env")
        return 1
    if not GCAL_SERVICE_ACCOUNT_FILE.is_file():
        print(f"Service account key not found: {GCAL_SERVICE_ACCOUNT_FILE}")
        return 1

    credentials = service_account.Credentials.from_service_account_file(
        str(GCAL_SERVICE_ACCOUNT_FILE), scopes=list(GCAL_SCOPES)
    )
    print(f"Service account: {credentials.service_account_email}")
    print(f"Calendar:        {GCAL_CALENDAR_ID}")
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    response = service.events().list(
        calendarId=GCAL_CALENDAR_ID,
        timeMin=datetime.now(timezone.utc).isoformat(),
        maxResults=10,
        singleEvents=True,
        orderBy="startTime",
        timeZone=DISPLAY_TZ_NAME,
    ).execute()
    print("\n=== NEXT 10 EVENTS ===")
    events = response.get("items", [])
    if not events:
        print("No upcoming events found.")
    for event in events:
        start = event.get("start", {})
        print(f"{start.get('dateTime', start.get('date', '?'))} | {event.get('summary', '(No title)')}")

    if args.write:
        start_time = datetime.combine(
            datetime.now(DISPLAY_TZ).date() + timedelta(days=1), time(10, 0), tzinfo=DISPLAY_TZ
        )
        body = {
            "summary": "Family Wall Service Account Test",
            "description": "Created and deleted by scripts/test_calendar.py.",
            "start": {"dateTime": start_time.isoformat(), "timeZone": DISPLAY_TZ_NAME},
            "end": {"dateTime": (start_time + timedelta(minutes=30)).isoformat(), "timeZone": DISPLAY_TZ_NAME},
            "reminders": {"useDefault": False},
        }
        created = service.events().insert(
            calendarId=GCAL_CALENDAR_ID, body=body, sendUpdates="none"
        ).execute()
        print(f"\n=== WRITE OK === inserted {created['id']}", end="")
        service.events().delete(
            calendarId=GCAL_CALENDAR_ID, eventId=created["id"], sendUpdates="none"
        ).execute()
        print(", deleted again")

    print("\nSERVICE ACCOUNT OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HttpError as error:
        print("Google Calendar API error:", error)
        sys.exit(1)
