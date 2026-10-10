"""集成密钥 / SMTP 口令只写：管理端响应不回明文，空值保留原值，clear_* 才清空。"""

from __future__ import annotations

import json
from typing import Any

import anyio
import httpx
import pytest
from fastapi import FastAPI

from app.core.file_config import write_json
from app.services import email_config as ec
from app.services import integrations_config as ic

_TOKENS = {
    "steam_api_key": "0123456789ABCDEF0123456789ABCDEF",
    "qq_app_key": "qqkey-0123456789abcdef-qqkq",
    "github_token": "github_pat_11AAAAAAA0123456789_zzzz",
    "pelican_client_token": "ptlc_abcdefghijklmnop1234",
    "pelican_application_token": "papp_abcdefghijklmnop5678",
}
_RCON_PASSWORD = "rcon-password-long-enough-1234"
_ALL_SECRETS = {**_TOKENS, "minecraft_rcon_password": _RCON_PASSWORD}
_SMTP_PASSWORD = "smtp-secret-password"


def _store_all() -> None:
    write_json(
        "integrations",
        {
            **_ALL_SECRETS,
            "qq_app_id": "101",
            "pelican_base_url": "https://panel.example.com",
            "pelican_server_uuid": "abcd1234",
            "minecraft_rcon_host": "127.0.0.1",
        },
    )


def _app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    from app.api import settings as settings_api
    from app.core.database import get_db
    from app.core.deps import require_admin

    monkeypatch.setattr(settings_api, "register_scheduler_jobs", lambda *args, **kwargs: None)
    app = FastAPI()
    app.include_router(settings_api.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[require_admin] = lambda: object()
    return app


def _call(app: FastAPI, method: str, url: str, **kwargs: Any) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    return anyio.run(_run)


def _assert_no_secret(text: str) -> None:
    for value in (*_ALL_SECRETS.values(), _SMTP_PASSWORD):
        assert value not in text


def test_public_integrations_never_echoes_secrets() -> None:
    _store_all()
    pub = ic.public_integrations(ic.load_integrations())
    _assert_no_secret(json.dumps(pub))
    for key in _ALL_SECRETS:
        assert pub[key] == ""
        assert pub[f"{key}_set"] is True
    for key, value in _TOKENS.items():
        assert pub[f"{key}_hint"] == value[-4:]
    assert "minecraft_rcon_password_hint" not in pub
    assert pub["steam_configured"] is True
    assert pub["qq_configured"] is True
    assert pub["github_configured"] is True
    assert pub["pelican_configured"] is True
    assert pub["minecraft_rcon_configured"] is True
    assert ic.get_steam_api_key() == _TOKENS["steam_api_key"]
    assert ic.get_github_token() == _TOKENS["github_token"]
    assert ic.get_qq_credentials() == ("101", _TOKENS["qq_app_key"])
    assert ic.get_minecraft_rcon_credentials()[2] == _RCON_PASSWORD


def test_hint_only_for_long_tokens() -> None:
    assert ic.secret_hint("y" * 12 + "abcd") == "abcd"
    assert ic.secret_hint("y" * 11 + "abcd") == ""
    assert ic.secret_hint("") == ""
    write_json("integrations", {"github_token": "short-token-123"})
    pub = ic.public_integrations(ic.load_integrations())
    assert pub["github_token_set"] is True
    assert pub["github_token_hint"] == ""
    assert pub["steam_api_key_set"] is False
    assert pub["steam_api_key_hint"] == ""


def test_save_keeps_blank_secrets_and_clears_only_on_flag() -> None:
    _store_all()
    blank: dict[str, Any] = {key: "" for key in ic.SECRET_FIELDS}
    blank.update({f"clear_{key}": False for key in ic.SECRET_FIELDS})
    ic.save_integrations(None, blank)
    ic.save_integrations(None, {key: None for key in ic.SECRET_FIELDS})
    cfg = ic.load_integrations()
    for key, value in _ALL_SECRETS.items():
        assert cfg[key] == value

    ic.save_integrations(None, {"github_token": "  new-github-token-0000  "})
    assert ic.get_github_token() == "new-github-token-0000"
    ic.save_integrations(None, {"clear_github_token": True, "github_token": "ignored-when-clearing"})
    assert ic.get_github_token() == ""
    ic.save_integrations(None, {"clear_minecraft_rcon_password": True})
    cfg = ic.load_integrations()
    assert cfg["minecraft_rcon_password"] == ""
    assert cfg["steam_api_key"] == _TOKENS["steam_api_key"]
    assert cfg["pelican_application_token"] == _TOKENS["pelican_application_token"]


def test_integrations_api_is_write_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _store_all()
    app = _app(monkeypatch)
    got = _call(app, "GET", "/api/settings/integrations")
    assert got.status_code == 200, got.text
    _assert_no_secret(got.text)
    body = got.json()
    assert body["github_token"] == ""
    assert body["github_token_set"] is True
    assert body["github_token_hint"] == _TOKENS["github_token"][-4:]
    assert body["pelican_application_token_hint"] == _TOKENS["pelican_application_token"][-4:]
    assert body["minecraft_rcon_password"] == ""
    assert body["minecraft_rcon_password_set"] is True

    saved = _call(app, "PUT", "/api/settings/integrations", json={"qq_app_id": "202"})
    assert saved.status_code == 200, saved.text
    _assert_no_secret(saved.text)
    cfg = ic.load_integrations()
    assert cfg["qq_app_id"] == "202"
    for key, value in _ALL_SECRETS.items():
        assert cfg[key] == value

    cleared = _call(app, "PUT", "/api/settings/integrations", json={"clear_steam_api_key": True})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["steam_api_key_set"] is False
    assert cleared.json()["steam_api_key_hint"] == ""
    assert ic.get_steam_api_key() == ""
    assert ic.get_github_token() == _TOKENS["github_token"]


def test_public_email_config_hides_password() -> None:
    ec.save_email_config(
        None,
        {
            "enabled": True,
            "smtp_user": "bot@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_password": _SMTP_PASSWORD,
        },
    )
    pub = ec.public_email_config(ec.load_email_config())
    assert pub["smtp_password"] == ""
    assert pub["smtp_password_set"] is True
    assert pub["configured"] is True
    _assert_no_secret(json.dumps(pub))

    ec.save_email_config(None, {"enabled": True, "smtp_password": "", "smtp_host": "smtp.example.com"})
    assert ec.load_email_config()["smtp_password"] == _SMTP_PASSWORD
    ec.save_email_config(None, {"clear_smtp_password": True, "smtp_password": "ignored-when-clearing"})
    assert ec.load_email_config()["smtp_password"] == ""


def test_email_api_is_write_only(monkeypatch: pytest.MonkeyPatch) -> None:
    base = {
        "enabled": True,
        "smtp_user": "bot@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
    }
    ec.save_email_config(None, {**base, "smtp_password": _SMTP_PASSWORD})
    app = _app(monkeypatch)

    got = _call(app, "GET", "/api/settings/email")
    assert got.status_code == 200, got.text
    _assert_no_secret(got.text)
    assert got.json()["smtp_password"] == ""
    assert got.json()["smtp_password_set"] is True
    assert got.json()["configured"] is True

    kept = _call(app, "PUT", "/api/settings/email", json={**base, "display_name": "战鸽"})
    assert kept.status_code == 200, kept.text
    _assert_no_secret(kept.text)
    assert kept.json()["display_name"] == "战鸽"
    assert ec.load_email_config()["smtp_password"] == _SMTP_PASSWORD

    refused = _call(app, "PUT", "/api/settings/email", json={**base, "clear_smtp_password": True})
    assert refused.status_code == 400
    assert refused.json()["detail"] == "请填写密码"
    assert ec.load_email_config()["smtp_password"] == _SMTP_PASSWORD

    cleared = _call(
        app,
        "PUT",
        "/api/settings/email",
        json={**base, "enabled": False, "clear_smtp_password": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["smtp_password_set"] is False
    assert ec.load_email_config()["smtp_password"] == ""

    replaced = _call(app, "PUT", "/api/settings/email", json={**base, "smtp_password": "new-pw"})
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["smtp_password"] == ""
    assert ec.load_email_config()["smtp_password"] == "new-pw"


def test_email_api_refuses_plaintext_auth_to_remote_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import email as email_service

    connects: list[str] = []
    monkeypatch.setattr(email_service.smtplib, "SMTP", lambda host, *a, **k: connects.append(host))
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", lambda host, *a, **k: connects.append(host))
    base = {
        "enabled": True,
        "smtp_user": "bot@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_port": 25,
        "smtp_password": _SMTP_PASSWORD,
    }
    refusal = ec.plaintext_auth_error("smtp.example.com", "NONE")
    app = _app(monkeypatch)

    refused = _call(app, "PUT", "/api/settings/email", json={**base, "encryption": "NONE"})
    assert refused.status_code == 400
    assert refused.json()["detail"] == refusal
    _assert_no_secret(refused.text)
    assert ec.load_email_config()["smtp_host"] == ""

    for payload, configured in (
        ({**base, "encryption": "STARTTLS", "smtp_port": 587}, True),
        ({**base, "encryption": "NONE", "smtp_host": "127.0.0.1"}, True),
        ({**base, "encryption": "NONE", "enabled": False}, False),
    ):
        saved = _call(app, "PUT", "/api/settings/email", json=payload)
        assert saved.status_code == 200, saved.text
        assert saved.json()["configured"] is configured

    write_json("email", {**base, "encryption": "NONE"})
    assert _call(app, "GET", "/api/settings/email").json()["configured"] is False
    tested = _call(app, "POST", "/api/settings/email/test", json={"to_email": "admin@example.com"})
    assert tested.status_code == 200, tested.text
    assert tested.json() == {"ok": False, "message": refusal}
    assert connects == []


def test_connection_tests_keep_saved_secret_on_saved_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.minecraft import pelican, rcon

    _store_all()
    pelican_calls: list[tuple[str, str]] = []
    rcon_calls: list[tuple[str, str]] = []

    def _get_server(base: str, token: str, server_uuid: str) -> dict[str, Any]:
        pelican_calls.append((base, token))
        return {"attributes": {"name": "srv"}}

    def _query_list(host: str, port: int, password: str) -> list[str]:
        rcon_calls.append((host, password))
        return []

    monkeypatch.setattr(pelican, "get_server", _get_server)
    monkeypatch.setattr(pelican, "get_resources", lambda *args: {})
    monkeypatch.setattr(rcon, "query_list", _query_list)
    app = _app(monkeypatch)
    pelican_url = "/api/settings/integrations/pelican-test"
    rcon_url = "/api/settings/integrations/minecraft-rcon-test"

    elsewhere = _call(app, "POST", pelican_url, json={"base_url": "https://evil.example/api/client"})
    assert elsewhere.json()["ok"] is False
    assert _call(app, "POST", pelican_url, json={}).json()["ok"] is True
    assert _call(app, "POST", pelican_url, json={"base_url": "https://panel.example.com/"}).json()["ok"] is True
    typed = _call(app, "POST", pelican_url, json={"base_url": "https://other.example", "token": "typed-token"})
    assert typed.json()["ok"] is True
    saved_token = _TOKENS["pelican_client_token"]
    assert pelican_calls == [
        ("https://panel.example.com", saved_token),
        ("https://panel.example.com", saved_token),
        ("https://other.example", "typed-token"),
    ]

    assert _call(app, "POST", rcon_url, json={"host": "10.0.0.9"}).json()["ok"] is False
    assert _call(app, "POST", rcon_url, json={}).json()["ok"] is True
    assert _call(app, "POST", rcon_url, json={"host": "10.0.0.9", "password": "typed"}).json()["ok"] is True
    assert rcon_calls == [("127.0.0.1", _RCON_PASSWORD), ("10.0.0.9", "typed")]
