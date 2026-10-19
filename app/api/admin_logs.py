"""LAN-only admin API: view and download the app's rotating log."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app import config, logging_setup
from app.envelope import envelope

router = APIRouter()

_MAX_TAIL_LINES = 5000


@router.get("/admin/logs")
def admin_logs(lines: int = Query(300, ge=1, le=_MAX_TAIL_LINES)) -> dict[str, Any]:
    """Tail of the current (today's) log file."""
    path = logging_setup.current_log_path()
    tail_lines, truncated = logging_setup.tail(path, lines)
    return envelope(
        {
            "file": path.name,
            "text": "\n".join(tail_lines),
            "line_count": len(tail_lines),
            "truncated": truncated,
            "exists": path.exists(),
        }
    )


@router.get("/admin/logs/files")
def admin_log_files() -> dict[str, Any]:
    """All log files (current + rotated), newest first, for the downloads list."""
    return envelope({"files": logging_setup.list_log_files()})


@router.get("/admin/logs/download")
def admin_log_download(name: str = Query(...)) -> FileResponse:
    """Download one log file as an attachment. Whitelisted to real log files."""
    if not logging_setup.is_log_file(name):
        raise HTTPException(status_code=400, detail="not a log file")
    path = (config.LOG_DIR / name).resolve()
    # Defence in depth: the resolved path must sit directly in LOG_DIR.
    if path.parent != config.LOG_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(path, media_type="text/plain", filename=name)
