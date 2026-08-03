"""Root logging: console + a daily-rotating file the admin page can show.

Kept separate from main.py so the wiring stays readable. The file handler rolls
at local midnight and prunes files older than LOG_RETENTION_DAYS, so the active
file is always today's and old days are downloadable until they age out.
"""

import logging
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app import config

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

#: Rotated files are "<LOG_FILE_NAME>.YYYY-MM-DD"; the active file has no suffix.
_ROTATED_SUFFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def configure_logging() -> None:
    """Attach a console + rotating-file handler to the root logger (idempotent)."""
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root.setLevel(level)

    # Idempotent: don't stack a second set of handlers if called twice (e.g. a
    # reload). Our handlers are tagged so we can recognise them.
    if any(getattr(h, "_dashboard", False) for h in root.handlers):
        return

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console._dashboard = True  # type: ignore[attr-defined]
    root.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        filename=current_log_path(),
        when="midnight",
        backupCount=config.LOG_RETENTION_DAYS,
        encoding="utf-8",
        delay=True,  # don't open the file until the first record is emitted
        utc=False,   # roll at *local* midnight, matching the display timezone
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    file_handler._dashboard = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)


def current_log_path() -> Path:
    """Path of the active (today's) log file."""
    return config.LOG_DIR / config.LOG_FILE_NAME


def is_log_file(name: str) -> bool:
    """True if ``name`` is the active file or a rotated ``.YYYY-MM-DD`` sibling.

    A whitelist check on the *name only* — the download endpoint uses this to
    refuse anything that isn't a real log file (path traversal included).
    """
    if name == config.LOG_FILE_NAME:
        return True
    prefix = config.LOG_FILE_NAME + "."
    if not name.startswith(prefix):
        return False
    return bool(_ROTATED_SUFFIX_RE.match(name[len(prefix):]))


def list_log_files() -> list[dict[str, object]]:
    """Every log file in LOG_DIR, newest first, with size and mtime.

    The active file is flagged ``is_current`` and sorts to the top.
    """
    out: list[dict[str, object]] = []
    if not config.LOG_DIR.exists():
        return out
    for path in config.LOG_DIR.iterdir():
        if not path.is_file() or not is_log_file(path.name):
            continue
        stat = path.stat()
        out.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified_utc": _mtime_iso(stat.st_mtime),
                "is_current": path.name == config.LOG_FILE_NAME,
            }
        )
    out.sort(key=lambda f: (not f["is_current"], f["name"]), reverse=False)
    # After the current file, show remaining (rotated) newest-date first.
    current = [f for f in out if f["is_current"]]
    rotated = sorted(
        (f for f in out if not f["is_current"]),
        key=lambda f: f["name"],
        reverse=True,
    )
    return current + rotated


def tail(path: Path, max_lines: int) -> tuple[list[str], bool]:
    """Last ``max_lines`` lines of ``path``. Returns (lines, truncated)."""
    if not path.exists():
        return [], False
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    if len(lines) > max_lines:
        return lines[-max_lines:], True
    return lines, False


def _mtime_iso(epoch: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
