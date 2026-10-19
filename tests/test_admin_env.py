"""Admin .env API: dry-run refuses a broken value, save backs up and writes.

The dry-run really spawns ``python -c "import app.config"`` against a
candidate file, so these are slower than the pure tests (~1 s each).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import env_admin
from app.main import app

ENV_TEXT = "# test env\r\nWEATHER_LAT=35.3238\r\nPHOTO_INTERVAL_SECONDS=10\r\n"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".env"
    path.write_bytes(ENV_TEXT.encode())
    monkeypatch.setattr(env_admin, "ENV_PATH", path)
    monkeypatch.setattr(env_admin, "BACKUP_DIR", tmp_path / "env-backups")
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_view_lists_example_sections_and_drift(env: Path, client: TestClient) -> None:
    data = client.get("/api/admin/env").json()["data"]
    keys = {k["key"]: k for s in data["sections"] for k in s["keys"]}
    assert keys["PHOTO_INTERVAL_SECONDS"]["value"] == "10"
    assert keys["PHOTO_INTERVAL_SECONDS"]["default"] == "10"
    assert keys["CAL_SCHOOL_URL"]["group"] == "CAL_SCHOOL"
    assert "FORECAST_DAYS" in data["drift"]["missing_in_env"]
    assert data["can_restart"] is False


def test_validate_refuses_a_broken_value_and_writes_nothing(env: Path, client: TestClient) -> None:
    res = client.post("/api/admin/env/validate", json={"changes": {"WEATHER_LAT": "abc"}})
    data = res.json()["data"]
    assert data["ok"] is False
    assert "WEATHER_LAT='abc'" in data["stderr_tail"]
    assert data["diff"] == {"WEATHER_LAT": {"old": "35.3238", "new": "abc"}}
    assert env.read_bytes() == ENV_TEXT.encode()


def test_save_refuses_a_broken_value(env: Path, client: TestClient) -> None:
    res = client.post("/api/admin/env/save",
                      json={"changes": {"CAL_SCHOOL_COLOR": "blue"}, "restart": True})
    data = res.json()["data"]
    assert data["ok"] is False and data["restarting"] is False
    assert "is not a #rrggbb colour" in data["stderr_tail"]
    assert env.read_bytes() == ENV_TEXT.encode()
    assert not env_admin.BACKUP_DIR.exists()


def test_save_backs_up_and_writes(env: Path, client: TestClient) -> None:
    res = client.post("/api/admin/env/save",
                      json={"changes": {"PHOTO_INTERVAL_SECONDS": "15"}, "restart": True})
    data = res.json()["data"]
    assert data["ok"] is True and data["restarting"] is False
    assert data["note"] == "restart the dev server by hand"
    assert env.read_bytes() == ENV_TEXT.replace("=10", "=15").encode()  # CRLF kept
    backups = list(env_admin.BACKUP_DIR.glob(".env.*"))
    assert len(backups) == 1 and backups[0].read_bytes() == ENV_TEXT.encode()


def test_backups_keep_only_the_newest(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(env_admin, "KEEP_BACKUPS", 2)
    for _ in range(4):
        env_admin._backup()
    assert len(list(env_admin.BACKUP_DIR.glob(".env.*"))) == 2


def test_invalid_key_names_are_refused_without_a_dry_run(env: Path) -> None:
    result = env_admin.validate({"BAD KEY": "x", "OK": "line\nbreak"})
    assert result["ok"] is False
    assert "not a valid KEY name" in result["stderr_tail"]
    assert "must be one line" in result["stderr_tail"]


def test_redaction_hides_urls_and_gcal_values() -> None:
    line = env_admin._redacted({"CAL_X_URL": "https://secret", "GCAL_CALENDAR_ID": "id",
                                "PHOTO_INTERVAL_SECONDS": "15", "CAL_X_LABEL": None})
    assert "secret" not in line and "=id" not in line
    assert "PHOTO_INTERVAL_SECONDS=15" in line and "CAL_X_LABEL=<removed>" in line


def test_save_of_a_subset_leaves_every_other_line_untouched(env: Path, client: TestClient) -> None:
    text = ENV_TEXT + "# keep me\r\nCAL_SCHOOL_COLOR=#74c0fc  # inline\r\n\r\nFORECAST_DAYS=4\r\n"
    env.write_bytes(text.encode())
    res = client.post("/api/admin/env/save", json={"changes": {"FORECAST_DAYS": "5"}})
    assert res.json()["data"]["ok"] is True
    assert env.read_bytes() == text.replace("FORECAST_DAYS=4", "FORECAST_DAYS=5").encode()


def test_hashes_show_a_saved_but_unapplied_env(
    env: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(env_admin, "LOADED_HASH", env_admin.file_hash())
    before = client.get("/api/admin/env").json()["data"]
    assert before["env_loaded_hash"] == before["env_file_hash"] != ""
    client.post("/api/admin/env/save", json={"changes": {"PHOTO_INTERVAL_SECONDS": "15"}})
    after = client.get("/api/admin/env").json()["data"]
    assert after["env_loaded_hash"] == before["env_loaded_hash"]
    assert after["env_file_hash"] != after["env_loaded_hash"]


def test_restart_endpoint_refuses_outside_nssm(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    exits: list[bool] = []
    monkeypatch.setattr(env_admin, "exit_soon", lambda: exits.append(True))
    monkeypatch.delenv("FAMILY_WALL_SERVICE", raising=False)
    data = client.post("/api/admin/restart").json()["data"]
    assert data == {"restarting": False, "note": "restart the dev server by hand"}
    monkeypatch.setenv("FAMILY_WALL_SERVICE", "1")
    assert client.post("/api/admin/restart").json()["data"] == {"restarting": True}
    assert exits == [True]
