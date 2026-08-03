"""The one JSON response shape every /api endpoint returns."""

from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Current UTC time as ISO8601 with a trailing ``Z``-style offset."""
    return datetime.now(timezone.utc).isoformat()


def envelope(data: Any, last_updated: str | None = None) -> dict[str, Any]:
    """Wrap ``data`` in the standard ``{"data": ..., "last_updated": ...}``."""
    return {"data": data, "last_updated": last_updated or utc_now_iso()}
