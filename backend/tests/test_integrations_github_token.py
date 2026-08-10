"""Tests for GitHub token in integrations_config (DB over env)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.core.crypto_secret import encrypt_secret
from app.services import integrations_config as ic


def _db_with_stored(stored: dict | None) -> MagicMock:
    db = MagicMock()
    row = None
    if stored is not None:
        row = MagicMock()
        row.value = json.dumps(stored, ensure_ascii=False)
    q = db.query.return_value
    q.filter.return_value.first.return_value = row
    return db


def test_github_token_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ic,
        "_env_defaults",
        lambda: {
            "steam_api_key": "",
            "qq_app_id": "",
            "qq_app_key": "",
            "napcat_base_url": "",
            "napcat_token": "",
            "github_token": "env-token",
        },
    )
    cfg = ic.load_integrations(_db_with_stored(None))
    assert cfg["github_token"] == "env-token"
    pub = ic.public_integrations(cfg)
    assert pub["github_token_set"] is True
    assert pub["github_configured"] is True


def test_github_token_db_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-github-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            ic,
            "_env_defaults",
            lambda: {
                "steam_api_key": "",
                "qq_app_id": "",
                "qq_app_key": "",
                "napcat_base_url": "",
                "napcat_token": "",
                "github_token": "env-token",
            },
        )
        enc = encrypt_secret("db-token")
        cfg = ic.load_integrations(_db_with_stored({"github_token": enc}))
        assert cfg["github_token"] == "db-token"
    finally:
        get_settings.cache_clear()


def test_clear_github_token_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret-key-for-github-token")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        monkeypatch.setattr(
            ic,
            "_env_defaults",
            lambda: {
                "steam_api_key": "",
                "qq_app_id": "",
                "qq_app_key": "",
                "napcat_base_url": "",
                "napcat_token": "",
                "github_token": "env-token",
            },
        )
        enc = encrypt_secret("db-token")
        db = _db_with_stored({"github_token": enc, "qq_app_id": "1"})
        # save with clear should pop and reload via load which falls back to env
        # Simulate stored after clear by having save mutate then load
        row = db.query.return_value.filter.return_value.first.return_value
        assert row is not None

        def _commit() -> None:
            # After clear, stored no longer has github_token
            stored = json.loads(row.value)
            assert "github_token" not in stored

        db.commit.side_effect = _commit
        out = ic.save_integrations(db, {"clear_github_token": True})
        assert out["github_token"] == "env-token"
    finally:
        get_settings.cache_clear()


def test_get_github_token_uses_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ic,
        "load_integrations",
        lambda _db: {"github_token": "from-db"},
    )
    assert ic.get_github_token(MagicMock()) == "from-db"
