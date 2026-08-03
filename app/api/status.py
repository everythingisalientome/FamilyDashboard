"""Dashboard-facing staleness endpoint powering the wall's stale-dot.

Cheap: reads fetch_meta and compares each active job's last success against its
refresh interval. The dashboard polls this on the shared data-refresh cadence.
"""

from typing import Any

from fastapi import APIRouter

from app import staleness
from app.envelope import envelope

router = APIRouter()


@router.get("/staleness")
def get_staleness() -> dict[str, Any]:
    return envelope(staleness.summary())
