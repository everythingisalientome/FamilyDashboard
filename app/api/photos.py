"""Photo slideshow listing. The files themselves are served from /photos."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter

from app.config import PHOTOS_DIR, PHOTO_EXTENSIONS
from app.envelope import envelope, utc_now_iso

router = APIRouter()


def list_photos() -> list[dict[str, Any]]:
    """Every displayable image in ``photos/``, sorted by filename."""
    if not PHOTOS_DIR.is_dir():
        return []

    photos: list[dict[str, Any]] = []
    for path in sorted(PHOTOS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in PHOTO_EXTENSIONS:
            continue
        photos.append(
            {
                "name": path.name,
                "url": f"/photos/{quote(path.name)}",
                "size": path.stat().st_size,
            }
        )
    return photos


def _folder_mtime_iso() -> str:
    """When the photo folder last changed, so the frontend can spot new drops."""
    if not PHOTOS_DIR.is_dir():
        return utc_now_iso()
    stamp = datetime.fromtimestamp(PHOTOS_DIR.stat().st_mtime, tz=timezone.utc)
    return stamp.isoformat()


@router.get("/photos")
def get_photos() -> dict[str, Any]:
    return envelope(list_photos(), last_updated=_folder_mtime_iso())
