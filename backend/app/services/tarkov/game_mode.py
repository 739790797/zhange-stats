"""逃离塔科夫 PVP / PVE。

上游：json.tarkov.dev `/regular/` 与 `/pve/`。
落库：各 tarkov_{resource}_raws 用 mode_id=1 存 PVP、mode_id=2 存 PVE；lang='' 主文件、lang=zh locale。
读路径靠 ContextVar，避免把 game_mode 逐层往下传。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TypeVar

from app.services.tarkov import sync_lock

logger = logging.getLogger(__name__)

GAME_MODES = ("pvp", "pve")
DEFAULT_GAME_MODE = "pvp"
ROW_ID_BY_MODE = {"pvp": 1, "pve": 2}
JSON_PREFIX_BY_MODE = {"pvp": "regular", "pve": "pve"}
JSON_API_ROOT = "https://json.tarkov.dev"

_current: ContextVar[str] = ContextVar("tarkov_game_mode", default=DEFAULT_GAME_MODE)

T = TypeVar("T")
E = TypeVar("E", bound=Exception)


def parse_game_mode(raw: str | None = None) -> str:
    """规范化为 pvp / pve。None 用当前 ContextVar。"""
    if raw is None:
        return _current.get()
    text = str(raw).strip().lower()
    if text in ("pve",):
        return "pve"
    if text in ("pvp", "regular", "pmc", ""):
        return "pvp"
    return DEFAULT_GAME_MODE


def current_game_mode() -> str:
    return _current.get()


def use_game_mode(mode: str) -> Token[str]:
    return _current.set(parse_game_mode(mode))


def reset_game_mode(token: Token[str]) -> None:
    _current.reset(token)


@contextmanager
def game_mode_scope(mode: str) -> Iterator[str]:
    parsed = parse_game_mode(mode)
    token = _current.set(parsed)
    try:
        yield parsed
    finally:
        _current.reset(token)


def raw_row_id(mode: str | None = None) -> int:
    return ROW_ID_BY_MODE[parse_game_mode(mode)]


def json_api_prefix(mode: str | None = None) -> str:
    return JSON_PREFIX_BY_MODE[parse_game_mode(mode)]


def json_resource_url(resource: str, *, lang: str | None = None, mode: str | None = None) -> str:
    prefix = json_api_prefix(mode)
    if lang:
        return f"{JSON_API_ROOT}/{prefix}/{resource}_{lang}"
    return f"{JSON_API_ROOT}/{prefix}/{resource}"


def cache_key(*parts: str) -> str:
    return ":".join((parse_game_mode(), *(p or "" for p in parts)))


def sync_modes(game_mode: str | None = None) -> tuple[str, ...]:
    if game_mode is not None:
        return (parse_game_mode(game_mode),)
    return GAME_MODES


def run_for_modes(
    fn: Callable[[], T],
    *,
    game_mode: str | None = None,
    error_cls: type[E],
    label: str,
) -> T:
    """按模式执行单栏目回源。未指定则 PVP、PVE 各跑一遍；全部失败才抛。

    持回源单飞锁：别处在回源时抛 sync_lock.TarkovSyncBusy；冷启动 ensure_* 已持锁则直接进。
    """
    last: T | None = None
    errors: list[str] = []
    with sync_lock.exclusive():
        for mode in sync_modes(game_mode):
            with game_mode_scope(mode):
                try:
                    last = fn()
                except error_cls as exc:
                    errors.append(f"{mode}: {exc}")
                    logger.warning("tarkov %s sync failed for %s: %s", label, mode, exc)
    if last is None:
        detail = "；".join(errors) if errors else "无结果"
        raise error_cls(f"{label}同步失败：{detail}")
    return last
