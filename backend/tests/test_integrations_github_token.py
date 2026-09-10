"""Tests for GitHub token in integrations_config (file over empty default)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.file_config import write_json
from app.services import integrations_config as ic


def test_github_token_defaults_empty() -> None:
    cfg = ic.load_integrations()
    assert cfg["github_token"] == ""
    pub = ic.public_integrations(cfg)
    assert pub["github_token_set"] is False
    assert pub["github_configured"] is False


def test_github_token_from_file() -> None:
    write_json("integrations", {"github_token": "file-token"})
    cfg = ic.load_integrations()
    assert cfg["github_token"] == "file-token"
    pub = ic.public_integrations(cfg)
    assert pub["github_configured"] is True


def test_clear_github_token() -> None:
    write_json("integrations", {"github_token": "file-token", "qq_app_id": "1"})
    out = ic.save_integrations(None, {"clear_github_token": True})
    assert out["github_token"] == ""
    assert out["qq_app_id"] == "1"


def test_get_github_token_uses_session() -> None:
    write_json("integrations", {"github_token": "from-file"})
    assert ic.get_github_token(MagicMock()) == "from-file"
