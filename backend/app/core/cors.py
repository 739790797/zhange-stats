"""浏览器 CORS：本地 Vite + Tauri 2 默认源。"""

from __future__ import annotations

# 本地 Vite 任意端口；Tauri 2 Windows 生产源 https://tauri.localhost，
# Linux/macOS 常见 tauri://localhost。可用 CORS_ORIGIN_REGEX 整段覆盖。
DEFAULT_CORS_ORIGIN_REGEX = (
    r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    r"https?://tauri\.localhost|"
    r"tauri://localhost)"
)


def resolve_cors_origin_regex(override: str | None = None) -> str:
    text = (override or "").strip()
    return text or DEFAULT_CORS_ORIGIN_REGEX
