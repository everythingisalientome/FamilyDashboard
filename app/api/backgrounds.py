"""Which pre-rendered ambient backgrounds exist under static/img/bg.

The frontend reads this once so it only ever requests a `<season>-<phase>.jpg`
that is actually present — combinations not yet generated fall back to the live
SVG scene without a 404. The images themselves are served by the static mount.
"""

from typing import Any

from fastapi import APIRouter

from app.config import STATIC_DIR
from app.envelope import envelope

router = APIRouter()

_BG_DIR = STATIC_DIR / "img" / "bg"
_BG_EXTENSIONS = {".jpg", ".jpeg"}


@router.get("/backgrounds")
def get_backgrounds() -> dict[str, Any]:
    """Sorted list of available background keys, e.g. ``["spring-noon", …]``."""
    keys: list[str] = []
    if _BG_DIR.is_dir():
        keys = sorted(
            path.stem
            for path in _BG_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in _BG_EXTENSIONS
        )
    return envelope(keys)
