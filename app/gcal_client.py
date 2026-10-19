"""The Google Calendar v3 client, shared by the family feed (fetchers/gcal.py)
and the importer's writer (gcal_writer.py).

Timeout: the service is built over an ``httplib2.Http(timeout=...)`` wrapped in
``AuthorizedHttp``, so every API call (and the token refresh) is bounded by
FETCH_TIMEOUT_SECONDS without touching the process-wide socket default.
"""

from typing import Any

from app.config import (
    FETCH_TIMEOUT_SECONDS,
    GCAL_CALENDAR_ID,
    GCAL_SCOPES,
    GCAL_SERVICE_ACCOUNT_FILE,
)


def config_problem() -> str | None:
    """Why the calendar can't be used, or None when it is configured."""
    if not GCAL_CALENDAR_ID:
        return "GCAL_CALENDAR_ID is not set"
    if not GCAL_SERVICE_ACCOUNT_FILE.is_file():
        return f"service account key not found: {GCAL_SERVICE_ACCOUNT_FILE}"
    return None


def build_service() -> Any:
    """A Calendar v3 client over a timeout-bounded, authorised httplib2.

    Imported lazily so a deploy that forgot ``pip install -r requirements.txt``
    still boots the wall; only the Google calls record the ImportError.
    """
    import httplib2
    from google.oauth2 import service_account
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_file(
        str(GCAL_SERVICE_ACCOUNT_FILE), scopes=list(GCAL_SCOPES)
    )
    http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=FETCH_TIMEOUT_SECONDS))
    return build("calendar", "v3", http=http, cache_discovery=False)


def http_status(exc: Exception) -> int | None:
    """The HTTP status of a googleapiclient ``HttpError``, else None."""
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None)
    return int(status) if status is not None else None
