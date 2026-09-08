"""浏览器 CORS：本地 Vite + Tauri 2 默认源。"""

from __future__ import annotations

# 本地 Vite 任意端口；可用 CORS_ORIGIN_REGEX 整段覆盖。生产同域一般不必 CORS。
DEFAULT_CORS_ORIGIN_REGEX = (
    r"(https?://(localhost|127\.0\.0\.1)(:\d+)?|"
    r"https?://tauri\.localhost|"
    r"tauri://localhost)"
)


def resolve_cors_origin_regex(
    override: str | None = None,
    *,
    production: bool = False,
) -> str | None:
    text = (override or "").strip()
    if text:
        return text
    if production:
        return None
    return DEFAULT_CORS_ORIGIN_REGEX
