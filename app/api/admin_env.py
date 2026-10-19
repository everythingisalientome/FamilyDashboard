"""LAN-only admin API: edit ``.env`` with a dry-run, then save (and restart).

Values are shown plain, the same as the source URLs on the status board: the
admin page is LAN-only and not for off-LAN exposure.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app import env_admin
from app.envelope import envelope

router = APIRouter()


class EnvChanges(BaseModel):
    #: KEY → new value, or null to remove the line.
    changes: dict[str, str | None]
    restart: bool = False


@router.get("/admin/env")
def admin_env() -> dict[str, Any]:
    """Every .env.example key by section, with the live value and drift."""
    return envelope(env_admin.view())


@router.post("/admin/env/validate")
def admin_env_validate(body: EnvChanges) -> dict[str, Any]:
    """Dry-run: import app.config from the candidate file. Nothing is written."""
    return envelope(env_admin.validate(body.changes))


@router.post("/admin/env/save")
def admin_env_save(body: EnvChanges) -> dict[str, Any]:
    """Re-validate, back up, atomically write .env; optionally exit for NSSM."""
    result = env_admin.save(body.changes)
    if not result["ok"] or not body.restart:
        return envelope(result | {"restarting": False})
    if not env_admin.can_restart():
        return envelope(result | {"restarting": False,
                                  "note": "restart the dev server by hand"})
    env_admin.exit_soon()
    return envelope(result | {"restarting": True})


@router.post("/admin/restart")
def admin_restart() -> dict[str, Any]:
    """Exit so NSSM relaunches us (applies a saved .env). Only under NSSM."""
    if not env_admin.can_restart():
        return envelope({"restarting": False, "note": "restart the dev server by hand"})
    env_admin.exit_soon()
    return envelope({"restarting": True})
