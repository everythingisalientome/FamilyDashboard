"""Display settings the frontend needs, so config.py stays the only source."""

from typing import Any

from fastapi import APIRouter

from app import config
from app.envelope import envelope

router = APIRouter()


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return envelope(
        {
            "timezone": config.DISPLAY_TZ_NAME,
            "photo_interval_seconds": config.PHOTO_INTERVAL_SECONDS,
            "photo_list_refresh_seconds": config.PHOTO_LIST_REFRESH_SECONDS,
            "nightly_reload_hour": config.NIGHTLY_RELOAD_HOUR,
            "data_refresh_seconds": config.DATA_REFRESH_SECONDS,
        }
    )
