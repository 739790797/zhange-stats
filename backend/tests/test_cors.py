"""默认 CORS 正则：本地 Vite 与 Tauri 2 壳源。"""

from __future__ import annotations

import re

from app.core.cors import DEFAULT_CORS_ORIGIN_REGEX, resolve_cors_origin_regex


def _fullmatch(origin: str) -> bool:
    return bool(re.compile(DEFAULT_CORS_ORIGIN_REGEX).fullmatch(origin))


def test_default_cors_allows_vite_and_tauri_origins() -> None:
    assert _fullmatch("http://localhost:6131")
    assert _fullmatch("http://127.0.0.1:5173")
    assert _fullmatch("https://localhost")
    assert _fullmatch("https://tauri.localhost")
    assert _fullmatch("http://tauri.localhost")
    assert _fullmatch("tauri://localhost")


def test_default_cors_rejects_unrelated_origins() -> None:
    assert not _fullmatch("https://evil.example")
    assert not _fullmatch("https://tauri.localhost.evil.com")
    assert not _fullmatch("http://192.168.1.2:6131")


def test_cors_origin_regex_override() -> None:
    custom = r"https://app\.example\.com"
    assert resolve_cors_origin_regex(custom) == custom
    assert resolve_cors_origin_regex("  ") == DEFAULT_CORS_ORIGIN_REGEX
    assert resolve_cors_origin_regex(None) == DEFAULT_CORS_ORIGIN_REGEX
