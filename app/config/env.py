"""Environment loading, the _env_* helpers, paths and logging.

Imported first by every other config module, so ``.env`` is loaded before any
setting is read.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Env helpers -----------------------------------------------------------
# Every tunable is read from the environment with the old hardcoded value as
# the fallback, so config.py stays the single place that names each setting
# while .env is where they are actually changed. A blank or unparseable value
# falls back to the default rather than crashing the process on boot.


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(k.strip() for k in _env_str(name, default).split(",") if k.strip())


# --- Paths -----------------------------------------------------------------

#: The repo root (this file is app/config/env.py).
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
STATIC_DIR: Path = BASE_DIR / "static"
PHOTOS_DIR: Path = BASE_DIR / "photos"
DATA_DIR: Path = BASE_DIR / "data"
DB_PATH: Path = DATA_DIR / "dashboard.db"

# --- Logging ---------------------------------------------------------------
# The app writes its own rotating log so the startup/fetch/admin lines are
# captured no matter how it is launched (dev server or NSSM service) and can be
# shown on the admin page. This is separate from NSSM's stdout capture.

#: Directory the log files live in. Defaults under data/ (git-ignored). Override
#: with an absolute path in .env to send logs elsewhere.
_LOG_DIR_RAW = _env_str("LOG_DIR", "")
LOG_DIR: Path = Path(_LOG_DIR_RAW) if _LOG_DIR_RAW else DATA_DIR / "logs"

#: Base name of the active log file. Rotated files get a ``.YYYY-MM-DD`` suffix.
LOG_FILE_NAME: str = "dashboard.log"

#: Root log level (DEBUG/INFO/WARNING/ERROR). Anything unrecognised → INFO.
LOG_LEVEL: str = _env_str("LOG_LEVEL", "INFO").upper()

#: How many past daily files to keep. The active file rolls at local midnight;
#: files older than this many days are pruned automatically.
LOG_RETENTION_DAYS: int = _env_int("LOG_RETENTION_DAYS", 14)
