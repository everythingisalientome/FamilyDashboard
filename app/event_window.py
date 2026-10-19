"""The date window the calendar fetchers cache and the month grid reads.

Shared by the ICS fetcher, the Google Calendar fetcher and /api/events so the
cache always covers exactly what the page can draw.
"""

from datetime import date, timedelta

from app.config import EVENT_HORIZON_DAYS


def grid_start(today: date) -> date:
    """First date the month grid can show — the week before the 1st."""
    return today.replace(day=1) - timedelta(days=7)


def fetch_window(today: date) -> tuple[date, date]:
    """(start, end) inclusive dates every calendar fetcher caches."""
    return grid_start(today), today + timedelta(days=EVENT_HORIZON_DAYS)
