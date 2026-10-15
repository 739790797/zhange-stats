"""SteamCMD 登录弹窗：口令只进这次控制台，状态里不出现。"""

from __future__ import annotations

import json
import queue
import sys
import time
from pathlib import Path

import anyio
import httpx
import pytest
from fastapi import FastAPI

from app.core.file_config import read_json, write_json
from app.services.integrations_config import load_integrations
from app.services.ror2 import steamcmd_login as login
from app.services.ror2.console_io import open_console
from app.services.ror2.steamcmd_login import classify_steamcmd_text


class _FakeConsole:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self._chunks: queue.Queue[str] = queue.Queue()
        self._exit: int | None = None
        self._chunks.put("Loading Steam API...OK\r\nSteam>\r\n")

    def read(self, timeout: float) -> str:
        try:
            return self._chunks.get(timeout=timeout)
        except queue.Empty:
            return ""

    def write(self, text: str) -> None:
        self.writes.append(text)
        lowered = text.lower()
        if lowered.startswith("login"):
            self._chunks.put("Steam Guard code:\r\n")
        elif text.strip() == "ABCDE":
            self._chunks.put("Waiting for user info...OK\r\n")
        elif lowered.startswith("quit"):
            self._exit = 0

    def poll(self) -> int | None:
        return self._exit

    def kill(self) -> None:
        self._exit = -9

    def wait(self, timeout: float) -> int:
        return 0 if self._exit is None else self._exit

    def close(self) -> None:
        self.kill()


@pytest.fixture(autouse=True)
def _reset_login():
    login.reset_login_for_tests()
    yield
    login.reset_login_for_tests()


def test_classify_guard_mobile_and_success() -> None:
    assert classify_steamcmd_text("Steam Guard code:") == "need_guard"
    assert classify_steamcmd_text("Two-factor code:") == "need_guard"
    assert classify_steamcmd_text("Please use the Steam Mobile App to confirm your sign in...") == "need_mobile"
    assert classify_steamcmd_text("Waiting for user info...OK") == "ok"
    assert classify_steamcmd_text("FAILED (Invalid Password)") == "error"
    assert classify_steamcmd_text("Loading Steam API...OK") is None


def test_login_keeps_the_password_out_of_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _FakeConsole()
    monkeypatch.setattr(login, "ensure_steamcmd", lambda: tmp_path / "steamcmd.exe")
    status = login.start_login(
        "alice",
        "secret-pass",
        console_factory=lambda _argv, cwd: fake,
    )
    assert status["state"] in {"starting", "need_guard"}
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and login.login_status()["state"] != "need_guard":
        time.sleep(0.02)
    current = login.login_status()
    assert current["state"] == "need_guard"
    assert "secret-pass" not in json.dumps(current)
    assert any("secret-pass" in item for item in fake.writes)
    login.submit_guard("ABCDE")
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and login.login_status()["state"] != "ok":
        time.sleep(0.02)
    assert login.login_status()["state"] == "ok"
    assert load_integrations()["steamcmd_username"] == "alice"
    assert "secret-pass" not in json.dumps(read_json("integrations"))


def test_load_drops_retired_steamcmd_secrets() -> None:
    write_json(
        "integrations",
        {
            "steamcmd_username": "alice",
            "steamcmd_password": "secret-pass",
            "steamcmd_guard_code": "ABCDE",
            "steamcmd_path": "C:/steamcmd/steamcmd.exe",
            "steamcmd_install_dir": "D:/Games/Risk of Rain 2",
        },
    )
    cfg = load_integrations()
    assert cfg["steamcmd_username"] == "alice"
    assert "steamcmd_password" not in cfg
    raw = json.dumps(read_json("integrations"))
    assert "secret-pass" not in raw
    assert "ABCDE" not in raw
    assert "steamcmd_install_dir" not in raw


def test_login_route_does_not_echo_the_password(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import settings as settings_api
    from app.core.database import get_db
    from app.core.deps import require_admin

    def fake_start(username: str, password: str, console_factory=None):
        assert password == "secret-pass"
        return {"state": "need_guard", "message": "请输入令牌"}

    monkeypatch.setattr("app.api.settings_steamcmd.start_login", fake_start)
    app = FastAPI()
    app.include_router(settings_api.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[require_admin] = lambda: object()

    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/settings/integrations/steamcmd/login",
                json={"username": "alice", "password": "secret-pass"},
            )

    got = anyio.run(_run)
    assert got.status_code == 200, got.text
    assert "secret-pass" not in got.text
    assert got.json()["state"] == "need_guard"


def test_console_roundtrip(tmp_path: Path) -> None:
    script = tmp_path / "echo_prompt.py"
    script.write_text(
        "import sys\nprint('Steam>', flush=True)\n"
        "line = sys.stdin.readline()\n"
        "print('ECHO ' + line.strip(), flush=True)\n",
        encoding="utf-8",
    )
    console = open_console([sys.executable, "-u", str(script)], cwd=str(tmp_path))
    try:
        seen = ""
        deadline = time.monotonic() + 8
        while "Steam>" not in seen and time.monotonic() < deadline:
            seen += console.read(0.2)
        assert "Steam>" in seen, repr(seen[:500])
        console.write("hello\r\n")
        deadline = time.monotonic() + 8
        while "ECHO hello" not in seen and time.monotonic() < deadline:
            seen += console.read(0.2)
        assert "ECHO hello" in seen, repr(seen[:500])
    finally:
        console.close()
