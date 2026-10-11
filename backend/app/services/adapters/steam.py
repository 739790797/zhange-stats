"""Steam Web API 适配器：拉取玩家当前在线/游玩状态。"""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.biz_logging import clear_log_until_change, log_until_change
from app.core.http_client import HttpRequestError, http_request
from app.core.security import strip_markup_chars
from app.services.adapters import BaseGameAdapter

logger = logging.getLogger(__name__)


def clean_persona_name(raw: Any) -> str | None:
    """Steam 昵称会当成员昵称展示：去掉尖括号，去完为空当没有。"""
    if raw is None:
        return None
    return strip_markup_chars(str(raw)).strip() or None


def _int_or_none(raw: Any) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _players(raw: Any) -> list[dict[str, Any]]:
    response = raw.get("response") if isinstance(raw, dict) else None
    players = response.get("players") if isinstance(response, dict) else None
    if not isinstance(players, list):
        return []
    return [p for p in players if isinstance(p, dict)]


def _steam_json(resp: httpx.Response, endpoint: str) -> dict[str, Any]:
    """4xx/5xx 与坏 JSON 转成固定文案（不回显上游正文，正文截断进日志）。"""
    log_key = f"steam-api:{endpoint}"
    if resp.status_code >= 400:
        log_until_change(
            logger,
            log_key,
            "Steam %s HTTP %s: %s",
            endpoint,
            resp.status_code,
            resp.text[:200],
        )
        raise RuntimeError(f"Steam API 请求失败（HTTP {resp.status_code}）")
    try:
        payload = resp.json()
    except ValueError as exc:
        log_until_change(logger, log_key, "Steam %s returned non-JSON", endpoint)
        raise RuntimeError("Steam API 返回无法解析") from exc
    if not isinstance(payload, dict):
        log_until_change(logger, log_key, "Steam %s returned non-object JSON", endpoint)
        raise RuntimeError("Steam API 返回格式无效")
    clear_log_until_change(log_key)
    return payload


@dataclass
class SteamPresence:
    steam_id: str
    persona_name: str | None
    persona_state: int | None
    game_id: str | None
    game_extra_info: str | None
    avatar_url: str | None = None

    @property
    def is_playing(self) -> bool:
        return bool(self.game_id)

    @property
    def status(self) -> str:
        """归一化为 offline / online / playing。"""
        if self.game_id:
            return "playing"
        if self.persona_state is None or self.persona_state == 0:
            return "offline"
        return "online"


@dataclass
class SteamPlayerProfile:
    steam_id: str
    persona_name: str | None
    avatar_url: str | None
    profile_url: str | None
    community_visibility_state: int | None
    persona_state: int | None

    @property
    def is_public(self) -> bool:
        # 3 = Public；私密/仅好友无法稳定拉取游戏详情与统计
        return self.community_visibility_state == 3


class SteamAdapter(BaseGameAdapter):
    game_key = "steam"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def fetch_raw(self, external_id: str) -> Any:
        return self.fetch_summaries([external_id])

    def parse(self, raw: Any) -> list[dict[str, Any]]:
        """通用解析接口；Presence 轮询使用 parse_presences。"""
        return []

    def fetch_summaries(self, steam_ids: list[str]) -> dict[str, Any]:
        if not steam_ids:
            return {"response": {"players": []}}
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")

        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamids": ",".join(steam_ids),
            }
        )
        url = (
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
            f"?{params}"
        )
        try:
            resp = http_request(
                "GET",
                url,
                headers={"User-Agent": "zhange-stats/1.0"},
                timeout=20,
            )
        except HttpRequestError as exc:
            raise RuntimeError(f"Steam API 网络错误: {exc}") from exc
        return _steam_json(resp, "GetPlayerSummaries")

    def fetch_player_profile(self, steam_id: str) -> SteamPlayerProfile:
        players = _players(self.fetch_summaries([steam_id]))
        if not players:
            raise ValueError("未找到该 Steam 账号")
        p = players[0]
        return SteamPlayerProfile(
            steam_id=str(p.get("steamid") or steam_id),
            persona_name=clean_persona_name(p.get("personaname")),
            avatar_url=p.get("avatarfull") or p.get("avatarmedium") or p.get("avatar"),
            profile_url=p.get("profileurl"),
            community_visibility_state=_int_or_none(p.get("communityvisibilitystate")),
            persona_state=_int_or_none(p.get("personastate")),
        )

    def fetch_owned_game_icons(self, steam_id: str) -> dict[str, str]:
        """拉取用户库游戏的客户端小图标（库列表名左侧那枚）。

        返回 app_id → 完整 CDN URL。资料未公开或无库时返回空 dict。
        """
        if not self.api_key:
            raise RuntimeError("STEAM_API_KEY 未配置")
        params = urllib.parse.urlencode(
            {
                "key": self.api_key,
                "steamid": steam_id,
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "format": "json",
            }
        )
        url = (
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
            f"?{params}"
        )
        try:
            resp = http_request(
                "GET",
                url,
                headers={"User-Agent": "zhange-stats/1.0"},
                timeout=30,
            )
        except HttpRequestError as exc:
            raise RuntimeError(f"Steam GetOwnedGames 网络错误: {exc}") from exc
        if resp.status_code in (401, 403):
            return {}
        raw = _steam_json(resp, "GetOwnedGames")

        response = raw.get("response")
        games = response.get("games") if isinstance(response, dict) else None
        result: dict[str, str] = {}
        for g in games if isinstance(games, list) else []:
            if not isinstance(g, dict):
                continue
            app_id = str(g.get("appid") or "").strip()
            icon_hash = str(g.get("img_icon_url") or "").strip()
            if not app_id or not icon_hash:
                continue
            result[app_id] = (
                "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/"
                f"{app_id}/{icon_hash}.jpg"
            )
        return result

    def parse_presences(self, raw: dict[str, Any]) -> list[SteamPresence]:
        result: list[SteamPresence] = []
        for p in _players(raw):
            game_id = p.get("gameid")
            result.append(
                SteamPresence(
                    steam_id=str(p.get("steamid", "")),
                    persona_name=clean_persona_name(p.get("personaname")),
                    persona_state=_int_or_none(p.get("personastate")),
                    game_id=str(game_id) if game_id else None,
                    game_extra_info=p.get("gameextrainfo"),
                    avatar_url=p.get("avatarfull")
                    or p.get("avatarmedium")
                    or p.get("avatar"),
                )
            )
        return result
