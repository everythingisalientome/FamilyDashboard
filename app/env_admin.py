"""The admin page's ``.env`` editor: view, dry-run, backup + atomic save.

Settings are imported by value at process start, so a change applies on a
restart (PLAN.md Phase 5, the env-vs-DB decision). Nothing is written unless a
fresh interpreter can import ``app.config`` from the candidate file in strict
mode — a typo is refused here rather than discovered by a wall that won't boot.
"""

import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import env_file
from app.config import BASE_DIR, DATA_DIR
from app.config.env import DOTENV_PATH
from app.env_file import Entry

log = logging.getLogger("dashboard.admin")

ENV_PATH: Path = DOTENV_PATH
EXAMPLE_PATH: Path = BASE_DIR / ".env.example"
BACKUP_DIR: Path = DATA_DIR / "env-backups"
KEEP_BACKUPS = 10
DRY_RUN_TIMEOUT = 20

_GROUP_RE = re.compile(
    r"^(CAL|PERSON)_(.+?)_(URL|LABEL|COLOR|ORDER|ALERT_COLOR|CLOSED_LABEL"
    r"|DISMISSAL_LABEL|FEEDS|KEYWORDS)$"
)
_SECRET_RE = re.compile(r"(_URL$|^GCAL_)")
_save_lock = threading.Lock()


def read(path: Path) -> list[Entry]:
    """Entries of ``path`` (empty if missing), line endings preserved."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return env_file.parse(fh.read())


def can_restart() -> bool:
    """True under NSSM: install-service.ps1 sets this marker in the service env."""
    return os.getenv("FAMILY_WALL_SERVICE", "") == "1"


def group_of(key: str) -> str | None:
    """``CAL_SCHOOL`` / ``PERSON_PRISHA`` for a feed's or person's keys."""
    match = _GROUP_RE.match(key)
    return f"{match.group(1)}_{match.group(2)}" if match else None


def _prefix(key: str) -> str:
    return "EVENT_STYLE_" if key.startswith("EVENT_STYLE_") else key.split("_")[0] + "_"


def view() -> dict[str, Any]:
    """The GET payload: sections of keys with value/default/comment, plus drift."""
    current, example = read(ENV_PATH), read(EXAMPLE_PATH)
    cur = env_file.values(current)
    sections = env_file.schema(example)
    by_prefix: dict[str, dict] = {}
    for section in sections:
        for item in section["keys"]:
            by_prefix.setdefault(_prefix(item["key"]), section)
            item.update(value=cur.get(item["key"], ""), in_env=item["key"] in cur, in_example=True)
    other = {"title": "Other (not in .env.example)", "intro": "", "keys": []}
    known = env_file.values(example)
    for key, value in cur.items():
        if key in known:
            continue
        item = {"key": key, "value": value, "default": None, "comment": "",
                "in_env": True, "in_example": False}
        by_prefix.get(_prefix(key), other)["keys"].append(item)
    if other["keys"]:
        sections.append(other)
    for section in sections:
        for item in section["keys"]:
            item["group"] = group_of(item["key"])
    return {
        "sections": sections,
        "drift": env_file.diff(current, example),
        "env_path": str(ENV_PATH),
        "can_restart": can_restart(),
    }


def _problems(changes: dict[str, str | None]) -> list[str]:
    bad = [f"{k!r} is not a valid KEY name" for k in changes if not env_file.KEY_RE.match(k)]
    bad += [f"{k}: value must be one line" for k, v in changes.items()
            if v is not None and ("\n" in v or "\r" in v)]
    return bad


def _python() -> str:
    venv = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.exists() else sys.executable


def _child_env(candidate: list[Entry]) -> dict[str, str]:
    """This process's env minus every .env-sourced key, so only the file counts.

    load_dotenv never overrides, and the running server already holds the old
    values in os.environ — inheriting them would vet the old file, not the new.
    """
    keys = set(env_file.values(candidate)) | set(env_file.values(read(ENV_PATH)))
    keys |= set(env_file.values(read(EXAMPLE_PATH))) | set(env_file.values(read(DOTENV_PATH)))
    drop = re.compile(r"^(CAL|PERSON|EVENT_STYLE|GCAL)_")
    env = {k: v for k, v in os.environ.items() if k not in keys and not drop.match(k)}
    return env | {"APP_CONFIG_STRICT": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def dry_run(candidate: list[Entry]) -> tuple[bool, str]:
    """Import app.config from the candidate file in a fresh strict interpreter."""
    fd, tmp = tempfile.mkstemp(prefix=".env.candidate-", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(env_file.render(candidate))
        env = _child_env(candidate) | {"APP_DOTENV_PATH": tmp}
        proc = subprocess.run(
            [_python(), "-c", "import app.config"], cwd=BASE_DIR, env=env,
            capture_output=True, text=True, timeout=DRY_RUN_TIMEOUT,
        )
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        return proc.returncode == 0, tail
    except subprocess.TimeoutExpired:
        return False, f"dry-run timed out after {DRY_RUN_TIMEOUT} s"
    finally:
        Path(tmp).unlink(missing_ok=True)


def validate(changes: dict[str, str | None]) -> dict[str, Any]:
    """Dry-run the candidate file. Nothing is written."""
    current = read(ENV_PATH)
    old = env_file.values(current)
    diff = {k: {"old": old.get(k), "new": v} for k, v in changes.items() if old.get(k) != v}
    bad = _problems(changes)
    if bad:
        return {"ok": False, "stderr_tail": "\n".join(bad), "diff": diff}
    ok, tail = dry_run(env_file.apply(current, changes))
    return {"ok": ok, "stderr_tail": tail, "diff": diff}


def _backup() -> Path | None:
    if not ENV_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = BACKUP_DIR / f".env.{stamp}"
    dest.write_bytes(ENV_PATH.read_bytes())
    for old in sorted(BACKUP_DIR.glob(".env.*"))[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)
    return dest


def _write_atomic(text: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".env.saving-", dir=ENV_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, ENV_PATH)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _redacted(changes: dict[str, str | None]) -> str:
    parts = []
    for key, value in changes.items():
        shown = "<removed>" if value is None else "<redacted>" if _SECRET_RE.search(key) else value
        parts.append(f"{key}={shown}")
    return ", ".join(parts)


def save(changes: dict[str, str | None]) -> dict[str, Any]:
    """Validate, back up, then atomically replace .env. Never a partial write."""
    with _save_lock:
        result = validate(changes)
        if not result["ok"]:
            log.warning("admin .env save refused (dry-run failed): %s", ", ".join(changes))
            return result
        current = read(ENV_PATH)
        backup = _backup()
        _write_atomic(env_file.render(env_file.apply(current, changes)))
        log.info("admin .env saved (%s): %s", backup.name if backup else "no backup",
                 _redacted(changes))
        return result | {"backup": str(backup) if backup else None}


def exit_soon(delay: float = 1.0) -> None:
    """Exit after the response is sent; NSSM (AppExit Restart) relaunches us."""
    def _bye() -> None:
        time.sleep(delay)
        log.info("admin: exiting for NSSM restart")
        logging.shutdown()
        os._exit(0)

    threading.Thread(target=_bye, name="admin-restart", daemon=True).start()
