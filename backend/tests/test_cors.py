"""本地浏览器 CORS 默认源与部署覆盖规则。"""

from __future__ import annotations

import re

import pytest

from app.core.cors import DEFAULT_CORS_ORIGIN_REGEX, resolve_cors_origin_regex


def _fullmatch(origin: str) -> bool:
    return bool(re.compile(DEFAULT_CORS_ORIGIN_REGEX).fullmatch(origin))


@pytest.mark.parametrize("origin", ["http://localhost:6131", "http://127.0.0.1:5173", "https://localhost"])
def test_default_cors_allows_local_vite_origins(origin: str) -> None:
    assert _fullmatch(origin)


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "https://localhost.evil.example", "http://192.168.1.2:6131"],
)
def test_default_cors_rejects_unrelated_origins(origin: str) -> None:
    assert not _fullmatch(origin)


@pytest.mark.parametrize("origin", ["https://tauri.localhost", "http://tauri.localhost", "tauri://localhost"])
def test_default_cors_rejects_retired_desktop_origins(origin: str) -> None:
    assert not _fullmatch(origin)


def test_cors_origin_regex_override() -> None:
    custom = r"https://app\.example\.com"
    assert resolve_cors_origin_regex(custom) == custom
    assert resolve_cors_origin_regex("  ") == DEFAULT_CORS_ORIGIN_REGEX
    assert resolve_cors_origin_regex(None) == DEFAULT_CORS_ORIGIN_REGEX
    assert resolve_cors_origin_regex(None, production=True) is None
    assert resolve_cors_origin_regex("  ", production=True) is None
    assert resolve_cors_origin_regex(custom, production=True) == custom
