"""签到 status force：HTTP 默认回源；绑定后回显回源，改偏好的回显读今日 logs。"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app

_STATUS_PATHS = (
    "/api/skland/status",
    "/api/taygedo/status",
    "/api/exilium/status",
    "/api/kujiequ/status",
)


def test_checkin_status_force_defaults_true() -> None:
    schema = app.openapi()
    paths = schema.get("paths") or {}
    for path in _STATUS_PATHS:
        op = (paths.get(path) or {}).get("get")
        assert op is not None, f"missing GET {path}"
        params = {p["name"]: p for p in (op.get("parameters") or []) if "name" in p}
        assert "force" in params, f"{path} missing force"
        assert params["force"].get("schema", {}).get("default") is True, path


@dataclass(frozen=True)
class _Platform:
    name: str
    module: str
    bind_path: str
    bind_body: dict[str, Any]
    bind_fn: str
    router_module: str | None = None
    prefs_fn_module: str | None = None


_PLATFORMS = (
    _Platform(
        "skland",
        "app.api.skland.checkin",
        "/bind",
        {"token": "skland-token"},
        "bind_skland",
        router_module="app.api.skland",
        prefs_fn_module="app.services.skland.checkin",
    ),
    _Platform(
        "taygedo",
        "app.api.taygedo",
        "/bind/json",
        {"credentials_json": '{"refresh_token": "r"}'},
        "bind_with_credentials_json",
    ),
    _Platform("kujiequ", "app.api.kujiequ", "/bind/token", {"token": "kujiequ-token"}, "bind_with_token"),
    _Platform(
        "exilium",
        "app.api.exilium",
        "/bind/password",
        {"account": "player@example.com", "password": "secret"},
        "bind_with_password",
    ),
    _Platform(
        "mihoyo",
        "app.api.mihoyo",
        "/bind/sms",
        {"phone": "13800000000", "captcha": "123456"},
        "bind_member_with_sms",
    ),
)

_MEMBER = SimpleNamespace(id=1, nickname="tester")
_BIND = SimpleNamespace(
    id=1,
    member_id=1,
    auto_checkin=True,
    checkin_hour=8,
    checkin_minute=0,
    bound_at=None,
    phone_mask=None,
)


def _client(monkeypatch: pytest.MonkeyPatch, p: _Platform) -> tuple[TestClient, list[object]]:
    from app.core import platform_deps
    from app.core.database import get_db
    from app.core.deps import get_current_user, require_user_member

    mod = importlib.import_module(p.module)
    forces: list[object] = []

    def query_today(db: Any, bind: Any, *, force: object) -> dict[str, Any]:
        forces.append(force)
        return {"results": []}

    monkeypatch.setattr(platform_deps, "is_feature_enabled", lambda db, feature_id: True)
    monkeypatch.setattr(mod, "get_bind_for_member", lambda db, member_id: _BIND)
    monkeypatch.setattr(mod, "query_today_for_bind", query_today)
    monkeypatch.setattr(mod, "preview_roles", lambda db, member: [])
    monkeypatch.setattr(mod, "apply_role_pref_update", lambda **kw: None)
    monkeypatch.setattr(mod, "apply_role_membership_replace", lambda **kw: None)
    monkeypatch.setattr(mod, p.bind_fn, lambda *a, **kw: None)
    monkeypatch.setattr(
        importlib.import_module(p.prefs_fn_module or p.module),
        "update_bind_prefs",
        lambda *a, **kw: None,
    )
    if hasattr(mod, "_member_or_404"):
        monkeypatch.setattr(mod, "_member_or_404", lambda db, user: _MEMBER)

    api = FastAPI()
    api.include_router(importlib.import_module(p.router_module or p.module).router, prefix="/api")
    api.dependency_overrides[get_db] = lambda: None
    api.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    api.dependency_overrides[require_user_member] = lambda: _MEMBER
    return TestClient(api), forces


@pytest.mark.parametrize("p", _PLATFORMS, ids=lambda p: p.name)
def test_status_echo_queries_upstream_only_for_display(
    monkeypatch: pytest.MonkeyPatch, p: _Platform
) -> None:
    client, forces = _client(monkeypatch, p)
    calls = (
        ("GET", "/status", None, True),
        ("POST", p.bind_path, p.bind_body, True),
        ("PATCH", "/bind", {"auto_checkin": True}, False),
        ("PATCH", "/role-prefs", {"game_code": "g", "role_uid": "1", "included": True}, False),
        ("PUT", "/role-memberships", {"roles": []}, False),
    )
    for method, path, body, expected in calls:
        forces.clear()
        resp = client.request(method, f"/api/{p.name}{path}", json=body)
        assert resp.status_code == 200, (method, path, resp.text)
        assert forces == [expected], (method, path)


def test_skland_qr_poll_ok_does_not_force_today_status(monkeypatch: pytest.MonkeyPatch) -> None:
    client, forces = _client(monkeypatch, _PLATFORMS[0])
    monkeypatch.setattr("app.api.skland.checkin.poll_qr_bind", lambda db, **kw: {"status": "ok"})
    resp = client.get("/api/skland/qr/poll", params={"scan_id": "scan-1234"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    assert forces == [False]
